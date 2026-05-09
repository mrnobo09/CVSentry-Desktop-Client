# Shared in-memory node state — extracted to break circular imports
# between routes.node_routes ↔ dependencies.auth

_node_state = {
    "node_id": None,
    "access_token": None,
    "refresh_token": None,
    "local_ip": None,
    "user_id": None,
    "user_email": None,
}

_cached_ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
