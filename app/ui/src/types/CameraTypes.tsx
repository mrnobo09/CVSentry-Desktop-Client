interface Camera{
    ip_address: string;
    onvif_url: string;
    rtsp_url: string;
}

interface Cameras {
    [key: string]: Camera;
}

export type { Camera, Cameras };