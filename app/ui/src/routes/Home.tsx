import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import CameraInfo from '../components/CameraInfo';
import type { Cameras, Camera, CameraStream } from '../types/CameraTypes';
import { PlayCircle, Database, Loader2 } from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL

// Internal type for UI rendering (includes the ID key)
interface CameraWithId extends Camera {
  id: string;
}

export default function Home() {
  const navigate = useNavigate();

  // State holds the camera objects plus their ID for UI mapping
  const [allCameras, setAllCameras] = useState<CameraWithId[]>([]);
  
  // State tracks selected cameras as a dictionary: { "cam_1": Camera, "cam_2": Camera }
  const [selectedCameras, setSelectedCameras] = useState<Cameras>({});
  
  const [isLoading, setIsLoading] = useState(true);
  const [isStarting, setIsStarting] = useState(false);

  // 1. Fetch Cameras
  useEffect(() => {
    setIsLoading(true);

    const fetchCameras = async () => {
      try {
        const response = await axios.get<Cameras>(`${BACKEND_URL}/cameras/list`);
        console.log(`Fetched cameras:`, JSON.stringify(response.data));
        
        const camerasArray = Object.entries(response.data).map(([key, data]) => ({
          id: key,
          ...data
        }));
        setAllCameras(camerasArray);
        console.log(`Processed cameras array:`, JSON.stringify(camerasArray));
      } catch(error) {
        console.error("Error fetching cameras:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchCameras();
  }, []);

  const handleCameraSelect = (cameraId: string) => {
    setSelectedCameras((prevSelected) => {
      // If already selected, remove it
      if (prevSelected[cameraId]) {
        const { [cameraId]: _removed, ...rest } = prevSelected;
        return rest;
      } else {
        // Add the camera to selected
        const cameraObj = allCameras.find((c) => c.id === cameraId);
        if (cameraObj) {
          // Extract only the Camera properties (without id)
          const { id: _ignoredId, ...cameraData } = cameraObj;
          return {
            ...prevSelected,
            [cameraId]: cameraData
          };
        }
        return prevSelected;
      }
    });
  };

  const handleStartAnalysis = async () => {
    if (Object.keys(selectedCameras).length === 0) return;
    
    setIsStarting(true);

    try {
      // selectedCameras is already in the correct format: { "cam_1": Camera, "cam_2": Camera }
      const payload = selectedCameras;

      // Send POST request with the formatted payload
      console.log("Sending payload:", JSON.stringify(payload, null, 2));
      
      await axios.post(`${BACKEND_URL}/cameras/start`, payload);

      // Navigate to streams page passing the IDs using CameraStream type
      const streamState: CameraStream = { 
        cameraIds: Object.keys(selectedCameras) 
      };
      navigate('/streams', { state: streamState });

    } catch (error) {
      console.error("Failed to start analysis:", error);
      alert("Failed to start analysis backend. Check console for details.");
    } finally {
      setIsStarting(false);
    }
  };

  const selectedCount = Object.keys(selectedCameras).length;

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-screen bg-gray-900 text-white gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <p>Scanning network for cameras...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-white">Camera Dashboard</h1>
          <p className="text-lg text-gray-400 mt-2">
            Select the cameras you wish to analyze or view.
          </p>
        </header>

        {/* Control Panel */}
        <div className="bg-gray-800 shadow-lg rounded-xl p-6 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4 sticky top-4 z-10 border border-gray-700">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-blue-400" />
            <span className="text-xl font-medium">
              {selectedCount}
              <span className="text-gray-400">
                {' '}
                {selectedCount === 1 ? 'camera' : 'cameras'} selected
              </span>
            </span>
          </div>
          
          <button
            onClick={handleStartAnalysis}
            disabled={selectedCount === 0 || isStarting}
            className={`flex items-center justify-center gap-2 w-full sm:w-auto bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold shadow-md transition-all duration-200 
              ${selectedCount === 0 || isStarting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700 hover:shadow-blue-900/30'}`}
          >
            {isStarting ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" />
                Initializing...
              </>
            ) : (
              <>
                <PlayCircle className="w-5 h-5" />
                Start Analyzing
              </>
            )}
          </button>
        </div>

        {/* Camera Grid */}
        {allCameras.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {allCameras.map((camera) => (
              <CameraInfo
                key={camera.id} 
                camera={camera}
                isSelected={camera.id in selectedCameras} 
                onSelect={() => handleCameraSelect(camera.id)} 
              />
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-500 py-12 border border-gray-800 rounded-xl bg-gray-800/30">
            <p className="text-lg font-semibold mb-2">No ONVIF cameras found.</p>
            <p className="text-sm">Please ensure your cameras are connected and support ONVIF discovery.</p>
          </div>
        )}
      </div>
    </div>
  );
}