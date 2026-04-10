#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# start.sh — Traffic Lab startup script (Linux / macOS)
# Usage: bash start.sh   or   chmod +x start.sh && ./start.sh
# ─────────────────────────────────────────────────────────────────

set -e  # exit on unexpected errors

echo ""
echo " =========================================="
echo "  Traffic Lab - Startup"
echo " =========================================="
echo ""

# ── HELPER: check if a port is free ──────────────────────────────
# Returns 0 (true) if free, 1 if in use
is_port_free() {
    local port=$1
    # Try ss first (modern Linux), fall back to netstat (macOS/older Linux)
    if command -v ss &>/dev/null; then
        ss -tuln 2>/dev/null | grep -q ":${port} " && return 1 || return 0
    elif command -v netstat &>/dev/null; then
        netstat -tuln 2>/dev/null | grep -q ":${port} " && return 1 || return 0
    else
        # lsof fallback
        lsof -i ":${port}" &>/dev/null && return 1 || return 0
    fi
}

# ── HELPER: validate port number ─────────────────────────────────
is_valid_port() {
    local port=$1
    # Must be a pure integer between 1 and 65535
    [[ "$port" =~ ^[0-9]+$ ]] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ]
}

# ── ASK FOR NGINX PORT ───────────────────────────────────────────
while true; do
    read -rp "Enter Nginx port (UI)  [default: 1225]: " NGINX_PORT
    NGINX_PORT="${NGINX_PORT:-1225}"   # use default if empty

    if ! is_valid_port "$NGINX_PORT"; then
        echo " [ERROR] \"$NGINX_PORT\" is not a valid port. Enter a number between 1 and 65535."
        continue
    fi

    if ! is_port_free "$NGINX_PORT"; then
        echo " [ERROR] Port $NGINX_PORT is already in use. Choose a different port."
        continue
    fi

    echo " [OK] Port $NGINX_PORT is free."
    break
done

# ── ASK FOR GRAFANA PORT ─────────────────────────────────────────
while true; do
    read -rp "Enter Grafana port        [default: 3000]: " GRAFANA_PORT
    GRAFANA_PORT="${GRAFANA_PORT:-3000}"

    if ! is_valid_port "$GRAFANA_PORT"; then
        echo " [ERROR] \"$GRAFANA_PORT\" is not a valid port. Enter a number between 1 and 65535."
        continue
    fi

    if [ "$GRAFANA_PORT" = "$NGINX_PORT" ]; then
        echo " [ERROR] Grafana port cannot be the same as Nginx port ($NGINX_PORT)."
        continue
    fi

    if ! is_port_free "$GRAFANA_PORT"; then
        echo " [ERROR] Port $GRAFANA_PORT is already in use. Choose a different port."
        continue
    fi

    echo " [OK] Port $GRAFANA_PORT is free."
    break
done

# ── SUMMARY ──────────────────────────────────────────────────────
echo ""
echo " =========================================="
echo "  Starting with:"
echo "    UI (Nginx)  →  http://localhost:${NGINX_PORT}"
echo "    Grafana     →  http://localhost:${GRAFANA_PORT}"
echo " =========================================="
echo ""

# ── WRITE .env FILE ──────────────────────────────────────────────
cat > .env <<EOF
NGINX_PORT=${NGINX_PORT}
GRAFANA_PORT=${GRAFANA_PORT}
EOF

echo " [INFO] Written .env file with ports."
echo " [INFO] Starting Docker Compose..."
echo ""

# ── START DOCKER COMPOSE ─────────────────────────────────────────
docker compose up --build
