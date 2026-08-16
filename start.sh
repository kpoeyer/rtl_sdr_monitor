#!/bin/bash
# RTL-SDR Multi-Protocol Monitor - Start Script
# Gebruik: ./start.sh [--no-sim] [--port 5000]

cd "$(dirname "$0")"
echo "📡 RTL-SDR Multi-Protocol Monitor"
echo "=================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python3 niet gevonden. Installeer Python 3.10+"
    exit 1
fi

# Install dependencies if needed
if ! python3 -c "import flask, flask_socketio, eventlet" 2>/dev/null; then
    echo "📦 Python dependencies installeren..."
    pip install -r requirements.txt -q
fi

# Check for rtl_test (SDR hardware)
if command -v rtl_test &>/dev/null; then
    echo "✅ RTL-SDR tools gevonden"
else
    echo "ℹ️  RTL-SDR tools niet gevonden (niet nodig voor simulatie)"
fi

echo ""
echo "🌐 Open http://localhost:${2:-5000} in je browser"
echo ""

# Start
exec python3 main.py "$@"