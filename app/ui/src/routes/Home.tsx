import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import request from '../utils/request';
import CameraInfo from '../components/CameraInfo';
import type { Cameras, Camera, CameraStream } from '../types/CameraTypes';
import {
  PlayCircle, Database, Loader2, RefreshCw, PlusCircle, X, Wifi, LogOut
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';

// Internal type for UI rendering (includes the ID key)
interface CameraWithId extends Camera {
  id: string;
  isManual?: boolean;
}

// --- Manual Add Modal ---
interface AddCameraModalProps {
  onClose: () => void;
  onAdd: (id: string, camera: Camera) => void;
}

function AddCameraModal({ onClose, onAdd }: AddCameraModalProps) {
  const [form, setForm] = useState({
    label: '',
    ip_address: '',
    rtsp_url: '',
    onvif_url: '',
  });
  const [error, setError] = useState('');

  const handleChange = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(f => ({ ...f, [key]: e.target.value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.rtsp_url.trim()) {
      setError('RTSP URL is required.');
      return;
    }
    const id = form.label.trim()
      ? form.label.trim().toLowerCase().replace(/\s+/g, '_')
      : `manual_${Date.now()}`;
    onAdd(id, {
      ip_address: form.ip_address.trim(),
      rtsp_url: form.rtsp_url.trim(),
      onvif_url: form.onvif_url.trim(),
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-2xl border border-gray-700 shadow-2xl w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <PlusCircle className="w-5 h-5 text-blue-400" />
            <h2 className="text-lg font-bold text-white">Add Camera Manually</h2>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-700 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {[
            { key: 'label', label: 'Camera Name / Label', placeholder: 'e.g. Front Door', required: false },
            { key: 'rtsp_url', label: 'RTSP URL *', placeholder: 'rtsp://192.168.1.10:554/stream', required: true },
            { key: 'ip_address', label: 'IP Address', placeholder: '192.168.1.10', required: false },
            { key: 'onvif_url', label: 'ONVIF URL', placeholder: 'http://192.168.1.10:8080/onvif/device_service', required: false },
          ].map(({ key, label, placeholder, required }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
              <input
                type="text"
                value={form[key as keyof typeof form]}
                onChange={handleChange(key as keyof typeof form)}
                placeholder={placeholder}
                required={required}
                className="w-full bg-gray-700/60 border border-gray-600 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition text-sm"
              />
            </div>
          ))}

          {error && (
            <p className="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg text-sm font-semibold transition-colors"
            >
              Add Camera
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// --- Main Home Component ---
export default function Home() {
  const navigate = useNavigate();
  const { logout } = useAuth();

  const [allCameras, setAllCameras] = useState<CameraWithId[]>([]);
  const [selectedCameras, setSelectedCameras] = useState<Cameras>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [lastFetchTime, setLastFetchTime] = useState<Date | null>(null);

  // Fetch discovered ONVIF cameras from FastAPI
  const fetchCameras = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setIsRefreshing(true);
    else setIsLoading(true);

    try {
      const data = await request.get<Cameras>('/cameras/list');
      const discovered: CameraWithId[] = Object.entries(data).map(([key, cam]) => ({
        id: key, ...cam,
      }));
      // Keep any manually added cameras that aren't already in the discovery result
      setAllCameras(prev => {
        const manualCameras = prev.filter(c => c.isManual);
        const discoveredIds = new Set(discovered.map(d => d.id));
        const uniqueManual = manualCameras.filter(m => !discoveredIds.has(m.id));
        return [...discovered, ...uniqueManual];
      });
      setLastFetchTime(new Date());
      console.log(`Fetched ${discovered.length} cameras`);
    } catch (error) {
      console.error('Error fetching cameras:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => { fetchCameras(); }, [fetchCameras]);

  // Add a manually-entered camera
  const handleAddManual = (id: string, camera: Camera) => {
    setAllCameras(prev => {
      // Replace if same id already exists
      const filtered = prev.filter(c => c.id !== id);
      return [...filtered, { id, ...camera, isManual: true }];
    });
  };

  const handleCameraSelect = (cameraId: string) => {
    setSelectedCameras(prev => {
      if (prev[cameraId]) {
        const { [cameraId]: _removed, ...rest } = prev;
        return rest;
      }
      const cameraObj = allCameras.find(c => c.id === cameraId);
      if (!cameraObj) return prev;
      const { id: _id, isManual: _manual, ...cameraData } = cameraObj;
      return { ...prev, [cameraId]: cameraData };
    });
  };

  const handleStartAnalysis = async () => {
    if (Object.keys(selectedCameras).length === 0) return;
    setIsStarting(true);
    try {
      await request.post('/cameras/start', selectedCameras);
      const streamState: CameraStream = { cameraIds: Object.keys(selectedCameras) };
      navigate('/streams', { state: streamState });
    } catch (error) {
      console.error('Failed to start analysis:', error);
      alert('Failed to start analysis. Check console for details.');
    } finally {
      setIsStarting(false);
    }
  };

  const selectedCount = Object.keys(selectedCameras).length;

  if (isLoading) {
    return (
      <div className="flex flex-col justify-center items-center h-screen bg-gray-900 text-white gap-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
        <p className="text-gray-400">Scanning network for cameras...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100 p-8">
      {showAddModal && (
        <AddCameraModal
          onClose={() => setShowAddModal(false)}
          onAdd={handleAddManual}
        />
      )}

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="mb-8 flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-4xl font-bold text-white">Camera Dashboard</h1>
            <p className="text-gray-400 mt-1 text-sm flex items-center gap-2">
              <Wifi className="w-3.5 h-3.5" />
              {allCameras.length} camera{allCameras.length !== 1 ? 's' : ''} found
              {lastFetchTime && (
                <span className="text-gray-600">· last scanned {lastFetchTime.toLocaleTimeString()}</span>
              )}
            </p>
          </div>
          {/* Action buttons */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => fetchCameras(true)}
              disabled={isRefreshing}
              title="Re-scan for ONVIF cameras"
              className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white px-4 py-2.5 rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              {isRefreshing ? 'Scanning...' : 'Re-scan'}
            </button>
            <button
              onClick={logout}
              title="Log Out"
              className="flex items-center gap-2 bg-red-600/20 hover:bg-red-600/30 border border-red-500/40 text-red-400 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              <LogOut className="w-4 h-4" />
              Log Out
            </button>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 text-blue-400 px-4 py-2.5 rounded-xl text-sm font-medium transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Add Manually
            </button>
          </div>
        </header>

        {/* Control Panel */}
        <div className="bg-gray-800 shadow-lg rounded-xl p-5 mb-8 flex flex-col sm:flex-row justify-between items-center gap-4 sticky top-4 z-10 border border-gray-700 backdrop-blur-sm bg-opacity-90">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-400" />
            <span className="text-lg font-medium">
              {selectedCount}
              <span className="text-gray-400 ml-1">
                {selectedCount === 1 ? 'camera' : 'cameras'} selected
              </span>
            </span>
          </div>
          <button
            onClick={handleStartAnalysis}
            disabled={selectedCount === 0 || isStarting}
            className={`flex items-center justify-center gap-2 w-full sm:w-auto bg-blue-600 text-white px-6 py-2.5 rounded-lg font-semibold shadow-md transition-all duration-200 
              ${selectedCount === 0 || isStarting ? 'opacity-50 cursor-not-allowed' : 'hover:bg-blue-700'}`}
          >
            {isStarting ? (
              <><Loader2 className="w-5 h-5 animate-spin" />Initializing...</>
            ) : (
              <><PlayCircle className="w-5 h-5" />Start Analyzing</>
            )}
          </button>
        </div>

        {/* Camera Grid */}
        {allCameras.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {allCameras.map(camera => (
              <div key={camera.id} className="relative">
                {camera.isManual && (
                  <span className="absolute top-2 right-2 z-10 text-[10px] bg-blue-600/80 text-white px-2 py-0.5 rounded-full uppercase tracking-wider font-semibold">
                    Manual
                  </span>
                )}
                <CameraInfo
                  camera={camera}
                  isSelected={camera.id in selectedCameras}
                  onSelect={() => handleCameraSelect(camera.id)}
                />
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-500 py-16 border border-gray-800 rounded-xl bg-gray-800/30">
            <Wifi className="w-12 h-12 mx-auto mb-4 opacity-20" />
            <p className="text-lg font-semibold mb-2">No ONVIF cameras discovered.</p>
            <p className="text-sm mb-6">Make sure your cameras are connected and support ONVIF discovery.</p>
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
            >
              <PlusCircle className="w-4 h-4" />
              Add Camera Manually
            </button>
          </div>
        )}
      </div>
    </div>
  );
}