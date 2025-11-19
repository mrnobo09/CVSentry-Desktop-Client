import base64

def jpeg_bytes_to_base64(jpeg_data: bytes, include_prefix: bool = False) -> str:
    """
    Converts raw JPEG bytes into a Base64 encoded string.
    
    Args:
        jpeg_data (bytes): The raw binary data of the JPEG image.
        include_prefix (bool): If True, adds 'data:image/jpeg;base64,' prefix 
                               so it can be used directly in <img src="...">.
    
    Returns:
        str: The Base64 string.
    """
    try:
        # 1. Encode bytes to base64 bytes
        b64_bytes = base64.b64encode(jpeg_data)
        
        # 2. Decode base64 bytes to UTF-8 string
        b64_string = b64_bytes.decode('utf-8')
        
        if include_prefix:
            return f"data:image/jpeg;base64,{b64_string}"
            
        return b64_string
        
    except Exception as e:
        print(f"Error converting JPEG to Base64: {e}")
        return ""

# # --- Example Usage (for testing) ---
# if __name__ == "__main__":
#     # Create a dummy white 1x1 pixel JPEG for testing
#     # (This represents what you get from Redis/cv2.imencode)
#     dummy_jpeg = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x15\x00\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xbf\x00\xff\xd9'

#     # Convert
#     result = jpeg_bytes_to_base64(dummy_jpeg, include_prefix=True)
    
#     print("Conversion Successful!")
#     print(f"Output snippet: {result[:50]}...")