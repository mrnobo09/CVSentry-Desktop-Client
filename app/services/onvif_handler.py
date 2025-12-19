import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from wsdiscovery import WSDiscovery
from wsdiscovery.qname import QName
from onvif import ONVIFCamera

def get_rtsp_url(xaddr, username, password):
    """Fetch RTSP stream URL from ONVIF service endpoint."""
    try:
        # Extract IP and Port from xaddr (ONVIF URL)
        parts = xaddr.split('/')
        ip_port = parts[2]
        
        if ':' in ip_port:
            ip, port = ip_port.split(':')
        else:
            ip, port = ip_port, 80 
        
        # Connect to Camera
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
        # print(f"Connection failed for {xaddr}: {e}")
        return None

def discover_cameras(username="admin", password="admin", discovery_timeout=3, retries=3):
    """
    Hybrid discovery: 
    1. Re-creates WSDiscovery per retry (Fixes single camera detection).
    2. Uses Threading for RTSP fetching (Fixes speed).
    """
    cameras = {}
    unique_services = {} # Key: IP, Value: XAddr
    
    onvif_type = QName("http://www.onvif.org/ver10/network/wsdl", "NetworkVideoTransmitter")
    
    # --- Phase 1: Reliable Discovery ---
    # We create a NEW WSDiscovery instance each loop. 
    # This ensures we don't have stale sockets or filtered results from previous runs.
    for i in range(retries):
        try:
            wsd = WSDiscovery()
            wsd.start()
            
            # Scan for devices
            services = wsd.searchServices(types=[onvif_type], timeout=discovery_timeout)
            
            for service in services:
                xaddr = service.getXAddrs()[0]
                ip = xaddr.split('/')[2].split(':')[0]
                
                if ip not in unique_services:
                    unique_services[ip] = xaddr
            
            wsd.stop()
            
            # Optimization: If we found devices, we don't necessarily need to stop.
            # But we continue retrying to find ANY missed devices (packet loss).
            
        except Exception as e:
            print(f"Error during discovery attempt {i}: {e}")

    # --- Phase 2: Fast Parallel Login ---
    camera_results = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_ip = {
            executor.submit(get_rtsp_url, xaddr, username, password): (ip, xaddr)
            for ip, xaddr in unique_services.items()
        }

        for future in as_completed(future_to_ip):
            ip, xaddr = future_to_ip[future]
            rtsp_url = future.result()
            
            if rtsp_url:
                camera_results.append({
                    "ip_address": ip,
                    "onvif_url": xaddr,
                    "rtsp_url": rtsp_url
                })

    # --- Phase 3: Output Formatting ---
    for i, cam_data in enumerate(camera_results):
        camera_id = f"cam_{i+1}"
        cameras[camera_id] = cam_data

    return cameras

# # Example Usage
# if __name__ == "__main__":
#     start = time.time()
    
#     # Default timeout 3s * 3 retries = Max 9s (but usually faster if devices found early)
#     cameras = discover_cameras(username="admin", password="admin") 
    
#     duration = time.time() - start
    
#     if cameras:
#         print(f"Discovered {len(cameras)} camera(s) in {duration:.2f}s")
#         for cam_id, info in cameras.items():
#             print(f"--- {cam_id} ---")
#             print(f"  IP Address: {info['ip_address']}")
#             print(f"  ONVIF URL:  {info['onvif_url']}")
#             print(f"  RTSP URL:   {info['rtsp_url']}")
#     else:
#         print("No cameras found.")