import { useState, useEffect, useRef } from 'react';
import mpegts from 'mpegts.js';
import { Maximize2, AlertCircle, Wifi, WifiOff } from 'lucide-react';

interface CameraFeedProps {
  cam_id: string;
}

export default function CameraFeed({ cam_id }: CameraFeedProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const playerRef = useRef<mpegts.Player | null>(null);

  const getStreamUrl = (id: string) => {
    const baseUrl = import.meta.env.VITE_BASE_RTMP_URL || 'http://localhost:8080/live';
    const cleanBase = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    return `${cleanBase}/${id}.flv`;
  };

  useEffect(() => {
    if (!mpegts.getFeatureList().mseLivePlayback) {
      setError('MSE Live Playback not supported');
      return;
    }

    let isMounted = true;
    let player: mpegts.Player | null = null;

    const initPlayer = async () => {
      try {
        const url = getStreamUrl(cam_id);
        
        player = mpegts.createPlayer({
          type: 'flv',
          url: url,
          isLive: true,
          hasAudio: false,
          cors: true,
        }, {
          enableWorker: true,
          enableStashBuffer: false,
          stashInitialSize: 128,
        });
        
        playerRef.current = player;

        if (videoRef.current && isMounted) {
          player.attachMediaElement(videoRef.current);
          player.load();
          
          try {
            await player.play();
            if (isMounted) {
                setIsConnected(true);
                setIsLoading(false);
            }
          } catch (playError) {
            if (isMounted && videoRef.current) {
              videoRef.current.muted = true;
              await player.play();
              setIsConnected(true);
              setIsLoading(false);
            }
          }
        }
      } catch (err) {
        if (isMounted) {
          console.error("Stream init error:", err);
          setError('Connection Failed');
          setIsConnected(false);
        }
      }
    };

    initPlayer();

    if (player) {
        (player as mpegts.Player).on(mpegts.Events.ERROR, (errType, errDetail) => {
            if (!isMounted) return;
            if (errType !== mpegts.ErrorTypes.NETWORK_ERROR) {
                console.error('Player Error:', errType, errDetail);
            }
        });
    }

    return () => {
      isMounted = false;
      if (player) {
        try {
          player.pause();
          player.unload();
          player.detachMediaElement();
          player.destroy();
        } catch (e) {
          // Ignore destruction errors
        }
        playerRef.current = null;
      }
    };
  }, [cam_id]);

  const handleFullscreen = () => {
    if (videoRef.current?.requestFullscreen) {
      videoRef.current.requestFullscreen();
    }
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
                <span className="text-green-400">Live Feed</span>
              ) : (
                'Connecting...'
              )}
            </p>
          </div>
        </div>
        
        <button
          onClick={handleFullscreen}
          disabled={!isConnected}
          className="p-2 hover:bg-gray-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Fullscreen"
        >
          <Maximize2 className="w-5 h-5 text-gray-400" />
        </button>
      </div>

      <div className="relative bg-black aspect-video flex items-center justify-center">
        <video
            ref={videoRef}
            className="w-full h-full object-contain"
            controls={false}
            playsInline
            muted={true}
        />

        {isLoading && !error && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/50 z-10">
            <div className="text-gray-300 text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto mb-2"></div>
                <p className="text-xs uppercase tracking-widest">Buffering...</p>
            </div>
            </div>
        )}

        {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-red-400 bg-gray-900/90 z-20">
            <AlertCircle className="w-12 h-12 mb-2" />
            <p className="text-sm font-semibold">{error}</p>
            <p className="text-xs text-gray-500 mt-1">Check media server</p>
            </div>
        )}

        {!isConnected && !isLoading && !error && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-600 z-10">
            <div className="text-center">
                <WifiOff className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Signal Lost</p>
            </div>
            </div>
        )}
      </div>
    </div>
  );
}