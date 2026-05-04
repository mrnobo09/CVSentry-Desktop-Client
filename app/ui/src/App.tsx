import { Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider, useAuth } from "./contexts/AuthContext"
import Home from "./routes/Home"
import CameraStreams from "./routes/CameraStreams"
import Login from "./screens/Login"
import VerifyOTP from "./screens/VerifyOTP"
import SyncStatusBar from "./components/SyncStatusBar"

function ProtectedRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/streams" element={<CameraStreams />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function PublicRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/verify-otp" element={<VerifyOTP />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

function AppContent() {
  const { isAuthenticated } = useAuth()

  // null = still checking auth (loading)
  if (isAuthenticated === null) {
    return <div className="min-h-screen bg-gray-900" />
  }

  return (
    <>
      {isAuthenticated ? <ProtectedRoutes /> : <PublicRoutes />}
      {isAuthenticated && <SyncStatusBar />}
    </>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App