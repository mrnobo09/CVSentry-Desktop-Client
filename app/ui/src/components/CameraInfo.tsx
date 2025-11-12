import type { Camera } from '../types/CameraTypes';
import { Wifi, Radio, Video, CheckCircle } from 'lucide-react';

// Define the props for this component
interface CameraInfoProps {
  camera: Camera;
  isSelected: boolean;
  onSelect: () => void; // Function to call when clicked
}

export default function CameraInfo({
  camera,
  isSelected,
  onSelect,
}: CameraInfoProps) {
  return (
    <div
      onClick={onSelect} // Make the whole card clickable
      className={`
        border p-4 rounded-xl bg-gradient-to-br from-gray-800 to-gray-900 
        transition-all duration-300 shadow-lg cursor-pointer
        w-full h-auto flex flex-col relative overflow-hidden
        ${
          isSelected
            ? 'border-blue-500 ring-2 ring-blue-500 shadow-blue-900/40'
            : 'border-gray-700 hover:border-blue-700 hover:shadow-blue-900/20'
        }
      `}
    >
      {/* --- Selection Checkmark --- */}
      {isSelected && (
        <div className="absolute top-2 right-2 bg-blue-600 text-white rounded-full p-1">
          <CheckCircle className="w-4 h-4" />
        </div>
      )}

      <div className="space-y-3 flex-1 flex flex-col justify-center pt-4">
        <div className="flex items-center gap-2 bg-gray-900/50 p-2 rounded-lg">
          <Wifi className="text-blue-400 w-4 h-4 flex-shrink-0" />
          <span className="text-blue-200 font-mono text-xs truncate" title={camera.ip_address}>
            {camera.ip_address}
          </span>
        </div>

        <div className="flex items-center gap-2 bg-gray-900/50 p-2 rounded-lg">
          <Radio className="text-cyan-400 w-4 h-4 flex-shrink-0" />
          <span className="text-blue-200 font-mono text-xs truncate" title={camera.onvif_url}>
            {camera.onvif_url}
          </span>
        </div>

        <div className="flex items-center gap-2 bg-gray-900/50 p-2 rounded-lg">
          <Video className="text-sky-400 w-4 h-4 flex-shrink-0" />
          <span className="text-blue-200 font-mono text-xs truncate" title={camera.rtsp_url}>
            {camera.rtsp_url}
          </span>
        </div>
      </div>
    </div>
  );
}