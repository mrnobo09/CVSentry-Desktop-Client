#!/bin/bash

# Stop and remove existing container if it exists
docker rm -f srs || true

# Run SRS
# -p 1935:1935 (RTMP)
# -p 1985:1985 (HTTP API)
# -p 8080:8080 (HTTP FLV/HLS)

echo "🚀 Starting Simple Realtime Server (SRS)..."
docker run -d --restart=always --name srs \
    -p 1935:1935 \
    -p 1985:1985 \
    -p 8080:8080 \
    ossrs/srs:5

echo "✅ SRS is running!"
echo "   - RTMP Publish: rtmp://localhost/live/STREAM_KEY"
echo "   - HTTP-FLV Play: http://localhost:8080/live/STREAM_KEY.flv"
