from pydantic import BaseModel,RootModel

class Camera(BaseModel):
    ip_address: str
    onvif_url: str
    rtsp_url: str | None = None

class Cameras(RootModel[dict[str, Camera]]):
    pass