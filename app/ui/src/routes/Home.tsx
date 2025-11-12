import { useState, useEffect } from 'react';
import axios from 'axios';
import CameraInfo from '../components/CameraInfo';
import type { Cameras, Camera } from '../types/CameraTypes';
import { PlayCircle, Database } from 'lucide-react';

export default function Home() {
  // State for all cameras discovered or fetched
  const [allCameras, setAllCameras] = useState<Camera[]>([]);
  // State for *only* the selected camera IPs
  const [selectedCameras, setSelectedCameras] = useState<string[]>([]);
  // State to know if we are loading initial data
  const [isLoading, setIsLoading] = useState(true);

  // On component mount: fetch cameras
  useEffect(() => {
    setIsLoading(true);

    const fetchCameras = async () => {
      try {
        const response = await axios.get<Cameras>(`http://127.0.0.1:8000/cameras/list`);
        setAllCameras(Object.values(response.data));
      } catch(error) {
        alert("Error fetching cameras from API. Please ensure the backend server is running.");
        console.error("Error fetching cameras:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchCameras();
  }, []);

  // Handles toggling a camera's selection state
  const handleCameraSelect = (cameraIp: string) => {
    setSelectedCameras((prevSelected) => {
      if (prevSelected.includes(cameraIp)) {
        // If already selected, remove it
        return prevSelected.filter((ip) => ip !== cameraIp);
      } else {
        // If not selected, add it
        return [...prevSelected, cameraIp];
      }
    });
  };

  // Handles the "Start Analyzing" button click
  const handleStartAnalysis = () => {
    console.log('Starting analysis on:', selectedCameras);
    alert(`Starting analysis on ${selectedCameras.length} camera(s).`);
    // You would navigate to a new page or open modals here
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-screen bg-gray-900 text-white">
        Loading configuration...
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

        {/* --- Control Panel --- */}
        <div className="bg-gray-800 shadow-lg rounded-xl p-6 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4 sticky top-4 z-10 border border-gray-700">
          <div className="flex items-center gap-3">
            <Database className="w-6 h-6 text-blue-400" />
            <span className="text-xl font-medium">
              {selectedCameras.length}
              <span className="text-gray-400">
                {' '}
                {selectedCameras.length === 1 ? 'camera' : 'cameras'} selected
              </span>
            </span>mport.meta.env.VITE_API_BASE_URL;
          </div>
          <button
            onClick={handleStartAnalysis}
            disabled={selectedCameras.length === 0}
            className="flex items-center justify-center gap-2 w-full sm:w-auto bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold shadow-md hover:bg-blue-700 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-blue-600"
          >
            <PlayCircle className="w-5 h-5" />
            Start Analyzing
          </button>
        </div>

        {/* --- Camera Grid --- */}
        {allCameras.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {allCameras.map((camera) => (
              <CameraInfo
                key={camera.ip_address}
                camera={camera}
                isSelected={selectedCameras.includes(camera.ip_address)}
                onSelect={() => handleCameraSelect(camera.ip_address)}
              />
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-500 py-12">
            <p className="text-lg">No cameras found.</p>
            <p>Please check your network or API connection.</p>
          </div>
        )}
      </div>
    </div>
  );
}