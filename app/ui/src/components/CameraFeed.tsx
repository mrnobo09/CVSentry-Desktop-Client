import { useState, useEffect, useRef } from 'react';
import { Maximize2, AlertCircle, Wifi, WifiOff } from 'lucide-react';

interface CameraFeedProps {
  cam_id: string;
}

export default function CameraFeed({ cam_id }: CameraFeedProps) {
  const [isConnected, setIsConnected] = useState(false);
  const [hasFirstFrame, setHasFirstFrame] = useState(false); 
  const [error, setError] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setIsConnected(false);
    setHasFirstFrame(false);
    setError(null);

    const WS_URL = `ws://127.0.0.1:4100/cameras/ws/${cam_id}`;
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`Connected to stream: ${cam_id}`);
      setIsConnected(true);
      setError(null);
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.image && canvasRef.current) {
          const ctx = canvasRef.current.getContext('2d');
          
          const img = new Image();
          img.onload = () => {
            if (canvasRef.current && ctx) {
          
                if (canvasRef.current.width !== img.width || canvasRef.current.height !== img.height) {
                    canvasRef.current.width = img.width;
                    canvasRef.current.height = img.height;
                }
                
                ctx.drawImage(img, 0, 0);
                setHasFirstFrame((prev) => {
                    if (!prev) return true;
                    return prev;
                });
            }
          };
          img.src = data.image;
        }
      } catch (err) {
        console.error("Frame parsing error:", err);
      }
    };
    
    ws.onerror = () => {
      console.error(`WebSocket error for ${cam_id}`);
      setError('Connection failed');
      setIsConnected(false);
    };
    
    ws.onclose = () => {
      console.log(`Stream closed: ${cam_id}`);
      setIsConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };

  }, [cam_id]); 

  const handleFullscreen = () => {
    if (canvasRef.current) {
      if (canvasRef.current.requestFullscreen) {
        canvasRef.current.requestFullscreen();
      }
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
                'Disconnected'
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
        {/* Canvas remains visible once hasFirstFrame is true */}
        <canvas
            ref={canvasRef}
            className={`w-full h-full object-contain ${!hasFirstFrame ? 'hidden' : 'block'}`}
        />

        {isConnected && !hasFirstFrame && !error && (
            <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-gray-500 text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500 mx-auto mb-2"></div>
                <p className="text-xs uppercase tracking-widest">Buffering...</p>
            </div>
            </div>
        )}

        {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-red-400 bg-gray-900/80">
            <AlertCircle className="w-12 h-12 mb-2" />
            <p className="text-sm font-semibold">{error}</p>
            <p className="text-xs text-gray-500 mt-1">Check server connection</p>
            </div>
        )}

        {!isConnected && !error && (
            <div className="absolute inset-0 flex items-center justify-center text-gray-600">
            <div className="text-center">
                <WifiOff className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Offline</p>
            </div>
            </div>
        )}
      </div>
    </div>
  );
}