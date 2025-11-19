import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer import AnalyzeCameraStreams
from schemas.cameras import Cameras, Camera


async def test_analyzer_with_real_camera():
    """Test analyzer with your actual camera."""
    
    print("=" * 60)
    print("CVSentry Analyzer - Real Camera Test")
    print("=" * 60 + "\n")
    
    # Create camera configuration with your camera
    test_cameras = Cameras(
        root={
            "cam_1": Camera(
                ip_address="192.168.0.124",
                onvif_url="http://192.168.0.124:8080/onvif/device_service",
                rtsp_url="rtsp://192.168.0.124:8080/h264_ulaw.sdp"
            )
        }
    )
    
    print("🎥 Camera Configuration:")
    for camera_id, camera_info in test_cameras.root.items():
        print(f"   - ID: {camera_id}")
        print(f"   - IP Address: {camera_info.ip_address}")
        print(f"   - ONVIF URL: {camera_info.onvif_url}")
        print(f"   - RTSP URL: {camera_info.rtsp_url}\n")
    
    print("📊 Starting analyzer...\n")
    
    try:
        # Start analyzing camera streams
        await AnalyzeCameraStreams(test_cameras.root)
        
        # Let it run for a specified duration
        test_duration = 120  # seconds
        print(f"⏱️  Running for {test_duration} seconds...\n")
        print("Monitor Redis in another terminal with:")
        print("  redis-cli")
        print("  > XLEN stream:camera_main")
        print("  > XREVRANGE stream:camera_main COUNT 5\n")
        
        await asyncio.sleep(test_duration)
        print("\n✓ Test completed successfully")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def test_analyzer_multi_camera():
    """Test analyzer with multiple cameras."""
    
    print("=" * 60)
    print("CVSentry Analyzer - Multi-Camera Test")
    print("=" * 60 + "\n")
    
    # Create configuration with multiple cameras
    test_cameras = Cameras(
        root={
            "cam_1": Camera(
                ip_address="192.168.0.119",
                onvif_url="http://192.168.0.119:8080/onvif/device_service",
                rtsp_url="rtsp://192.168.0.119:8080/h264_ulaw.sdp"
            ),
            "cam_2": Camera(
                ip_address="192.168.0.124",
                onvif_url="http://192.168.0.124:8080/onvif/device_service",
                rtsp_url="rtsp://192.168.0.124:8080/h264_ulaw.sdp"
            )
        }
    )
    
    print("🎥 Camera Configuration:")
    for camera_id, camera_info in test_cameras.root.items():
        print(f"   - ID: {camera_id}")
        print(f"   - IP: {camera_info.ip_address} | ONVIF: {camera_info.onvif_url}")
        print(f"   - RTSP: {camera_info.rtsp_url}\n")
    
    print("📊 Starting analyzer...\n")
    
    try:
        # Start analyzing camera streams
        await AnalyzeCameraStreams(test_cameras)
        
        test_duration = 60  # seconds
        print(f"⏱️  Running for {test_duration} seconds...\n")
        
        await asyncio.sleep(test_duration)
        print("\n✓ Multi-camera test completed successfully")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test runner."""
    print("\nSelect test mode:\n")
    print("1. Single Camera Test (Recommended)")
    print("2. Multi-Camera Test")
    print("3. Exit")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    if choice == "1":
        await test_analyzer_with_real_camera()
    elif choice == "2":
        await test_analyzer_multi_camera()
    elif choice == "3":
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice. Please try again.")
        await main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        sys.exit(1)