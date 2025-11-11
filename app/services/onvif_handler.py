from wsdiscovery import WSDiscovery
from wsdiscovery.qname import QName
from onvif import ONVIFCamera

def discover_cameras():
    cameras = {}
    try:
        onvif_type = QName(
            "http://www.onvif.org/ver10/network/wsdl",
            "NetworkVideoTransmitter"
        )

        wsd = WSDiscovery()
        wsd.start()
        services = wsd.searchServices(types=[onvif_type], timeout=5)
        wsd.stop()

        for i, service in enumerate(services):
            xaddr = service.getXAddrs()[0]
            ip_address = xaddr.split('/')[2].split(':')[0]
            camera_id = f"cam_{i+1}"
            cameras[camera_id] = {
                "ip_address": ip_address,
                "onvif_ip": xaddr
            }

    except Exception as e:
        print(f"Error during discovery: {e}")

    return cameras


def get_rtsp_url(onvif_url, username, password):
    """Fetch RTSP stream URL from ONVIF service endpoint."""
    try:
        parts = onvif_url.split('/')
        ip_port = parts[2]
        if ':' in ip_port:
            ip, port = ip_port.split(':')
        else:
            ip, port = ip_port, 80 

        cam = ONVIFCamera(ip, int(port), username, password) 
        media_service = cam.create_media_service()

        profiles = media_service.GetProfiles()
        token = profiles[0].token

        stream_setup = {
            'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
            'ProfileToken': token
        }
        uri = media_service.GetStreamUri(stream_setup)
        return uri.Uri
    except Exception as e:
        print(f"Failed to get RTSP URL: {e}")
        return None


# if __name__ == "__main__":
#     cameras = discover_cameras()
#     for cam_id, info in cameras.items():
#         print(f"\nDiscovered {cam_id}: {info['onvif_ip']}")
#         rtsp = get_rtsp_url(info['onvif_ip'], username="admin", password="admin")
#         if rtsp:
#             print(f"RTSP URL: {rtsp}")
#         else:
#             print("Could not fetch RTSP URL.")
