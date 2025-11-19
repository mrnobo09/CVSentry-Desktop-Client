interface Camera{
    ip_address: string;
    onvif_url: string;
    rtsp_url: string;
}

interface Cameras {
    [key: string]: Camera;
}

interface CameraStream {
    cameraIds: string[];
}

export type { Camera, Cameras, CameraStream };