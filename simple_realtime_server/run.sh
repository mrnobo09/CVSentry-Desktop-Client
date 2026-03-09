#!/bin/bash

# Load environment variables from the desktop app .env
ENV_FILE="../app/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Detect the LAN IP automatically (the interface used to reach the internet)
if [ -z "$SRS_CANDIDATE" ]; then
    CANDIDATE=$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
    if [ -z "$CANDIDATE" ]; then
        CANDIDATE="127.0.0.1"
    fi
else
    CANDIDATE="$SRS_CANDIDATE"
fi

SRS_RTMP_PORT=${SRS_RTMP_PORT:-1935}
SRS_HTTP_PORT=${SRS_HTTP_PORT:-8080}
SRS_API_PORT=${SRS_API_PORT:-1985}
SRS_RTC_PORT=${SRS_RTC_PORT:-8000}

echo "📡 Using CANDIDATE IP: $CANDIDATE"

# Stop and remove existing container if it exists
docker rm -f srs || true

echo "🚀 Starting Simple Realtime Server (SRS) with WebRTC + HTTP-FLV..."
docker run -d --restart=always --name srs \
    -e CANDIDATE="$CANDIDATE" \
    -p ${SRS_RTMP_PORT}:1935 \
    -p ${SRS_API_PORT}:1985 \
    -p ${SRS_HTTP_PORT}:8080 \
    -p ${SRS_RTC_PORT}:8000/udp \
    -v "$(pwd)/srs.conf:/usr/local/srs/conf/srs.conf" \
    ossrs/srs:5

echo "✅ SRS is running!"
echo "   - RTMP Publish  : rtmp://localhost:${SRS_RTMP_PORT}/live/STREAM_KEY"
echo "   - HTTP-FLV Play : http://localhost:${SRS_HTTP_PORT}/live/STREAM_KEY.flv"
echo "   - WebRTC (WHEP) : http://localhost:${SRS_API_PORT}/rtc/v1/play/?app=live&stream=STREAM_KEY"
echo "   - CANDIDATE IP  : $CANDIDATE"
