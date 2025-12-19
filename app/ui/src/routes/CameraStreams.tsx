import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { StopCircle, Grid3x3, AlertTriangle } from 'lucide-react';
import CameraFeed from '../components/CameraFeed';
import type { CameraStream } from '../types/CameraTypes';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL

export default function CameraStreams() {
  const navigate = useNavigate();
  const location = useLocation();
  
  // Extract cameraIds from location state using CameraStream type
  const state = location.state as CameraStream | null;
  const cameraIds = state?.cameraIds || [];
  
  const [isAnalyzing, setIsAnalyzing] = useState(true);
  const [isStopping, setIsStopping] = useState(false);

  // Handle stopping all analysis
  const handleStopAnalysis = async () => {
    if (isStopping) return;
    
    setIsStopping(true);
    setIsAnalyzing(false);
    console.log('Stopping analysis on all cameras...');

    try {
      await fetch(`${BACKEND_URL}/cameras/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cameras: cameraIds }),
      });
      console.log('Backend workers stopped successfully');
    } catch (error) {
      console.error('Failed to stop backend analysis:', error);
      // We continue to navigate even if the API fails, to not trap the user
    }

    // Navigate back to home
    navigate('/');
  };

  if (cameraIds.length === 0) {
    return (
      <div className="flex flex-col justify-center items-center h-screen bg-gray-900 text-white gap-4">
        <AlertTriangle className="w-12 h-12 text-yellow-500" />
        <p className="text-xl">No cameras selected for streaming.</p>
        <button
          onClick={() => navigate('/')}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-all"
        >
          Back to Dashboard
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
      <div className="max-w-full mx-auto">
        {/* Header */}
        <header className="mb-8">
          <h1 className="text-4xl font-bold text-white">Live Camera Analysis</h1>
          <p className="text-lg text-gray-400 mt-2">
            Monitoring {cameraIds.length} camera{cameraIds.length !== 1 ? 's' : ''} in real-time
          </p>
        </header>

        {/* Control Panel */}
        <div className="bg-gray-800 shadow-lg rounded-xl p-6 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4 sticky top-4 z-10 border border-gray-700 backdrop-blur-sm bg-opacity-90">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-3 h-3 rounded-full ${isAnalyzing ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
              <span className="text-lg font-medium">
                {isAnalyzing ? 'Live Analysis Active' : 'Analysis Stopped'}
              </span>
            </div>
            <div className="hidden sm:flex items-center gap-2 text-gray-400 border-l border-gray-600 pl-4">
              <Grid3x3 className="w-5 h-5" />
              <span>{cameraIds.length} Active Feeds</span>
            </div>
          </div>
          
          <button
            onClick={handleStopAnalysis}
            disabled={isStopping}
            className={`flex items-center justify-center gap-2 w-full sm:w-auto px-6 py-3 rounded-lg font-semibold shadow-md transition-all duration-200 ${
              isStopping 
                ? 'bg-gray-600 cursor-not-allowed text-gray-300'
                : 'bg-red-600 text-white hover:bg-red-700 hover:shadow-red-900/20'
            }`}
          >
            {isStopping ? (
              <>Stopping...</>
            ) : (
              <>
                <StopCircle className="w-5 h-5" />
                Stop Analysis
              </>
            )}
          </button>
        </div>

        {/* Camera Feed Grid */}
        <div className={`grid gap-6 ${
          cameraIds.length === 1 
            ? 'grid-cols-1 max-w-4xl mx-auto' // Centers the single feed
            : cameraIds.length === 2
            ? 'grid-cols-1 lg:grid-cols-2'
            : 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4'
        }`}>
          {cameraIds.map((cam_id) => (
            <CameraFeed
              key={cam_id}
              cam_id={cam_id}
            />
          ))}
        </div>
      </div>
    </div>
  );
}