import { useState, useEffect, useRef } from 'react';
import { Maximize2, AlertCircle, Wifi, WifiOff, Eye, EyeOff } from 'lucide-react';

interface FrameMetadata {
    weapon?: any[];
    face?: any[];
    combined_threat?: boolean;
}

interface CameraFeedProps {
    cam_id: string;
}

const SKELETON = [
    [5, 7], [7, 9], [6, 8], [8, 10],
    [5, 6], [5, 11], [6, 12], [11, 12],
    [11, 13], [13, 15], [12, 14], [14, 16],
] as const;

function drawOverlay(
    ctx: CanvasRenderingContext2D,
    metadata: FrameMetadata | null,
    video: HTMLVideoElement,
    canvas: HTMLCanvasElement,
) {
    const vw = video.videoWidth || 640;
    const vh = video.videoHeight || 480;
    const displayW = video.clientWidth;
    const displayH = video.clientHeight;

    if (canvas.width !== displayW || canvas.height !== displayH) {
        canvas.width = displayW;
        canvas.height = displayH;
    }

    ctx.clearRect(0, 0, displayW, displayH);
    if (!metadata) return;

    const scaleX = displayW / vw;
    const scaleY = displayH / vh;
    const allDets = [...(metadata.weapon || []), ...(metadata.face || [])];

    for (const det of allDets) {
        const box = det.box;
        if (!box || box.length !== 4) continue;
        const [x1, y1, x2, y2] = box;
        const sx1 = x1 * scaleX, sy1 = y1 * scaleY;
        const sx2 = x2 * scaleX, sy2 = y2 * scaleY;

        let color = '#00ff00';
        const label = det.class_name;
        if (label === 'THREAT_AIMING') color = '#ff0000';
        else if (label === 'person_pose') {
            if (det.is_aiming) color = '#ff0000';
            else if (det.has_weapon) color = '#ff8c00';
            else color = '#00e5ff'; // Cyan
        } else if (['pistol', 'rifle', 'knife', 'weapon'].includes(label?.toLowerCase())) color = '#ff0000';
        else if (label === 'COMBINED_THREAT') color = '#0000dc';
        else if (label === 'known_face') color = '#00dc64';
        else if (label === 'face') color = '#00ff00'; // Green

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.strokeRect(sx1, sy1, sx2 - sx1, sy2 - sy1);

        let text = `${label} ${(det.score || 0).toFixed(2)}`;
        if (label === 'known_face' && det.identity) {
            text = `${det.identity} (${(det.rec_confidence || 0).toFixed(2)})`;
        } else if (label === 'COMBINED_THREAT') {
            text = `ARMED: ${det.identity || 'Unknown'}`;
        } else if (label === 'person_pose' && det.is_aiming) {
            text = 'WEAPON THREAT';
        }
        ctx.fillStyle = color;
        const tw = ctx.measureText(text).width;
        ctx.fillRect(sx1, Math.max(sy1 - 20, 0), tw + 4, 20);
        ctx.fillStyle = '#fff';
        ctx.font = '12px monospace';
        ctx.fillText(text, sx1 + 2, Math.max(sy1 - 6, 14));

        if (det.keypoints) {
            const kps = det.keypoints;
            for (const [p1, p2] of SKELETON) {
                if (p1 < kps.length && p2 < kps.length) {
                    const pt1 = kps[p1], pt2 = kps[p2];
                    if (pt1[0] > 0 && pt2[0] > 0 && !isNaN(pt1[0]) && !isNaN(pt2[0])) {
                        ctx.beginPath();
                        ctx.moveTo(pt1[0] * scaleX, pt1[1] * scaleY);
                        ctx.lineTo(pt2[0] * scaleX, pt2[1] * scaleY);
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 2;
                        ctx.stroke();
                    }
                }
            }
            for (let i = 0; i < kps.length; i++) {
                if (kps[i][0] > 0 && !isNaN(kps[i][0])) {
                    ctx.beginPath();
                    ctx.arc(kps[i][0] * scaleX, kps[i][1] * scaleY, 3, 0, Math.PI * 2);
                    ctx.fillStyle = (i === 9 || i === 10) && det.has_weapon ? '#ff0000' : color;
                    ctx.fill();
                }
            }
        }

        if (det.is_aiming && det.aiming_vec) {
            const midX = (sx1 + sx2) / 2, midY = (sy1 + sy2) / 2;
            ctx.beginPath();
            ctx.moveTo(midX, midY);
            ctx.lineTo(midX + det.aiming_vec[0] * 200 * scaleX, midY + det.aiming_vec[1] * 200 * scaleY);
            ctx.strokeStyle = '#ff0000';
            ctx.lineWidth = 4;
            ctx.stroke();
        }
    }

    if (metadata.combined_threat) {
        ctx.fillStyle = 'rgba(255,0,0,0.15)';
        ctx.fillRect(0, 0, displayW, 4);
    }
}

export default function CameraFeed({ cam_id }: CameraFeedProps) {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [overlayEnabled, setOverlayEnabled] = useState(true);
    const [metadata, setMetadata] = useState<FrameMetadata | null>(null);

    const videoRef = useRef<HTMLVideoElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const pcRef = useRef<RTCPeerConnection | null>(null);
    const animRef = useRef<number>(0);
    const metadataRef = useRef<FrameMetadata | null>(null);

    useEffect(() => {
        let pc: RTCPeerConnection;
        let isMounted = true;

        async function connect() {
            try {
                const fastapiBase = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001';
                const token = localStorage.getItem('access_token') || '';

                let iceServers = [{ urls: 'stun:stun.l.google.com:19302' }];
                try {
                    const iceResp = await fetch(
                        `${fastapiBase}/config/ice-servers?token=${encodeURIComponent(token)}`,
                    );
                    if (iceResp.ok) {
                        const iceConfig = await iceResp.json();
                        if (iceConfig.iceServers && iceConfig.iceServers.length) {
                            iceServers = iceConfig.iceServers;
                        }
                    }
                } catch {}

                pc = new RTCPeerConnection({ iceServers });
                pcRef.current = pc;

                pc.addTransceiver('video', { direction: 'recvonly' });
                pc.addTransceiver('audio', { direction: 'recvonly' });

                pc.createDataChannel('detections');

                pc.ondatachannel = (evt) => {
                    evt.channel.onmessage = (msg) => {
                        try {
                            const data = JSON.parse(msg.data);
                            if (data.type === 'metadata') {
                                metadataRef.current = data.detections || null;
                                setMetadata(data.detections || null);
                            }
                        } catch {}
                    };
                };

                pc.ontrack = (evt) => {
                    if (!isMounted || !videoRef.current) return;
                    if (evt.streams?.[0]) {
                        videoRef.current.srcObject = evt.streams[0];
                        videoRef.current.play().catch(() => {
                            if (videoRef.current) {
                                videoRef.current.muted = true;
                                videoRef.current.play().catch(() => {});
                            }
                        });
                        setIsConnected(true);
                        setIsLoading(false);
                    }
                };

                pc.oniceconnectionstatechange = () => {
                    if (!isMounted) return;
                    if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
                        setError('Connection lost');
                        setIsConnected(false);
                    }
                };

                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);

                const whepUrl = `${fastapiBase}/webrtc/${cam_id}/whep?token=${encodeURIComponent(token)}`;
                const resp = await fetch(whepUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/sdp' },
                    body: pc.localDescription!.sdp,
                });

                if (!resp.ok) throw new Error(`WHEP error ${resp.status}`);
                const answerSdp = await resp.text();
                await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp });
            } catch (err: any) {
                if (isMounted) {
                    setError(err?.message || 'Connection failed');
                    setIsConnected(false);
                    setIsLoading(false);
                }
            }
        }

        connect();

        return () => {
            isMounted = false;
            if (pcRef.current) {
                pcRef.current.close();
                pcRef.current = null;
            }
            if (videoRef.current) videoRef.current.srcObject = null;
        };
    }, [cam_id]);

    useEffect(() => {
        function renderLoop() {
            const video = videoRef.current;
            const canvas = canvasRef.current;
            if (video && canvas) {
                const ctx = canvas.getContext('2d');
                if (ctx) {
                    if (overlayEnabled && metadataRef.current) {
                        drawOverlay(ctx, metadataRef.current, video, canvas);
                    } else {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                    }
                }
            }
            animRef.current = requestAnimationFrame(renderLoop);
        }
        animRef.current = requestAnimationFrame(renderLoop);
        return () => cancelAnimationFrame(animRef.current);
    }, [overlayEnabled]);

    const handleFullscreen = () => {
        videoRef.current?.requestFullscreen?.();
    };

    return (
        <div className="bg-gray-800 rounded-xl overflow-hidden shadow-lg border border-gray-700 hover:border-gray-600 transition-all duration-200">
            <div className="bg-gray-750 px-4 py-3 flex items-center justify-between border-b border-gray-700">
                <div className="flex items-center gap-3">
                    {isConnected ? (
                        <Wifi className="w-5 h-5 text-green-500 animate-pulse" />
                    ) : (
                        <WifiOff className="w-5 h-5 text-red-500" />
                    )}
                    <div>
                        <h3 className="font-semibold text-white uppercase tracking-wider">{cam_id.replace('_', ' ')}</h3>
                        <p className="text-xs text-gray-400 flex items-center gap-1">
                            {error ? (
                                <span className="text-red-400">{error}</span>
                            ) : isConnected ? (
                                <span className="text-green-400">Live WebRTC Feed</span>
                            ) : (
                                'Connecting...'
                            )}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setOverlayEnabled(!overlayEnabled)}
                        className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
                        title={overlayEnabled ? 'Hide overlays' : 'Show overlays'}
                    >
                        {overlayEnabled ? (
                            <Eye className="w-4 h-4 text-green-400" />
                        ) : (
                            <EyeOff className="w-4 h-4 text-gray-500" />
                        )}
                    </button>
                    <button
                        onClick={handleFullscreen}
                        disabled={!isConnected}
                        className="p-2 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        title="Fullscreen"
                    >
                        <Maximize2 className="w-5 h-5 text-gray-400" />
                    </button>
                </div>
            </div>

            <div className="relative bg-black aspect-video flex items-center justify-center">
                <video
                    ref={videoRef}
                    className="w-full h-full object-contain"
                    controls={false}
                    playsInline
                    muted={true}
                />
                <canvas
                    ref={canvasRef}
                    className="absolute top-0 left-0 w-full h-full pointer-events-none z-10"
                />

                {isLoading && !error && (
                    <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-20">
                        <div className="text-gray-300 text-center">
                            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto mb-2" />
                            <p className="text-xs uppercase tracking-widest">Connecting WebRTC...</p>
                        </div>
                    </div>
                )}

                {error && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center text-red-400 bg-gray-900/90 z-20">
                        <AlertCircle className="w-12 h-12 mb-2" />
                        <p className="text-sm font-semibold">{error}</p>
                    </div>
                )}
            </div>
        </div>
    );
}
