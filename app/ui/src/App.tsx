import { Routes, Route } from "react-router-dom"
import Home from "./routes/Home"
import CameraStreams from "./routes/CameraStreams"

function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<Home/>} />
        <Route path="/streams" element={<CameraStreams/>} />
      </Routes>
    </>
  )
}

export default App