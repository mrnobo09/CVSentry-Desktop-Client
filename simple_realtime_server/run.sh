#!/bin/bash

# Load environment variables from the desktop app .env
ENV_FILE="../app/.env"
if [ -f "$ENV_FILE" ]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
fi

# Load SRS-specific env
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
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
SRS_API_PASSWORD=${SRS_API_PASSWORD:-""}

echo "📡 Using CANDIDATE IP: $CANDIDATE"

# Ensure cvsentry-net Docker network exists for callback communication
docker network create cvsentry-net 2>/dev/null || true

# Stop and remove existing container if it exists
docker rm -f srs || true

# Substitute placeholder in srs.conf with actual password
TMP_CONF=$(mktemp)
sed "s/__SRS_API_PASSWORD__/${SRS_API_PASSWORD}/g" "$SCRIPT_DIR/srs.conf" > "$TMP_CONF"

echo "🚀 Starting Simple Realtime Server (SRS) with WebRTC + HTTP-FLV..."
docker run -d --restart=always --name srs \
    --network cvsentry-net \
    -e CANDIDATE="$CANDIDATE" \
    -p ${SRS_RTC_PORT}:8000/udp \
    -v "$TMP_CONF:/usr/local/srs/conf/srs.conf" \
    ossrs/srs:5

# Cleanup temp conf after container starts
rm -f "$TMP_CONF"

echo "✅ SRS is running!"
echo "   - RTMP Publish  : rtmp://srs:${SRS_RTMP_PORT}/live/STREAM_KEY (internal network only)"
echo "   - HTTP-FLV Play : via orchestrator proxy (not directly exposed)"
echo "   - WebRTC (WHEP) : via orchestrator proxy (not directly exposed)"
echo "   - WebRTC Media  : udp://${CANDIDATE}:${SRS_RTC_PORT} (ICE-protected)"
echo "   - CANDIDATE IP  : $CANDIDATE"
