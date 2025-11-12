from wsdiscovery import WSDiscovery
from wsdiscovery.qname import QName
from onvif import ONVIFCamera # Assuming this is available

def get_rtsp_url(onvif_url, username, password):
    """Fetch RTSP stream URL from ONVIF service endpoint."""
    try:
        # Extract IP and Port from the ONVIF URL (e.g., http://192.168.1.10:80/onvif/device_service)
        parts = onvif_url.split('/')
        ip_port = parts[2]
        
        if ':' in ip_port:
            ip, port = ip_port.split(':')
        else:
            ip, port = ip_port, 80 
        
        # Instantiate the ONVIF Camera object
        cam = ONVIFCamera(ip, int(port), username, password) 
        
        # Create media service proxy and fetch the stream URI
        media_service = cam.create_media_service()
        profiles = media_service.GetProfiles()
        
        # Use the first profile found
        token = profiles[0].token 

        stream_setup = {
            'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': {'Protocol': 'RTSP'}},
            'ProfileToken': token
        }
        uri = media_service.GetStreamUri(stream_setup)
        return uri.Uri
    except Exception as e:
        print(f"Failed to get RTSP URL for {onvif_url}: {e}")
        return None


def discover_cameras(username="admin", password="admin", discovery_timeout=5):
    """
    Discovers ONVIF cameras and fetches their RTSP stream URLs.

    Args:
        username (str): Default username for the camera login.
        password (str): Default password for the camera login.
        discovery_timeout (int): Timeout in seconds for WS-Discovery search.

    Returns:
        dict: A dictionary of cameras, including IP, ONVIF URL, and RTSP URL.
    """
    cameras = {}
    
    try:
        # 1. WS-Discovery Phase
        onvif_type = QName(
            "http://www.onvif.org/ver10/network/wsdl",
            "NetworkVideoTransmitter"
        )

        wsd = WSDiscovery()
        wsd.start()
        # Use the provided timeout
        services = wsd.searchServices(types=[onvif_type], timeout=discovery_timeout)
        wsd.stop()

        # 2. RTSP Fetching Phase
        for i, service in enumerate(services):
            xaddr = service.getXAddrs()[0]
            ip_address = xaddr.split('/')[2].split(':')[0]
            camera_id = f"cam_{i+1}"
            
            # Fetch the RTSP URL using the helper function
            rtsp_url = get_rtsp_url(xaddr, username, password)

            cameras[camera_id] = {
                "ip_address": ip_address,
                "onvif_url": xaddr,
                "rtsp_url": rtsp_url  # <-- RTSP URL is now part of the camera object
            }

    except Exception as e:
        print(f"Error during discovery: {e}")

    return cameras


# Example usage for verification:
# if __name__ == "__main__":
#     # NOTE: Replace 'admin'/'admin' with your actual camera credentials
#     cameras = discover_cameras(username="admin", password="admin") 
#     
#     if cameras:
#         print(f"Successfully discovered {len(cameras)} camera(s).")
#         for cam_id, info in cameras.items():
#             print(f"--- {cam_id} ---")
#             print(f"  IP Address: {info['ip_address']}")
#             print(f"  ONVIF URL:  {info['onvif_url']}")
#             print(f"  RTSP URL:   {info['rtsp_url']}")
#     else:
#         print("No ONVIF cameras found or an error occurred.")