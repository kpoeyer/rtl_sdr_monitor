#!/usr/bin/env python3
"""
RTL-SDR Multi-Protocol Monitor
================================
Web-based GUI for monitoring ADS-B, ACARS, AIS, POCSAG, P2000 & ERMES
using an RTL-SDR receiver on Linux.

Usage:
    python main.py            # starts on http://0.0.0.0:5000
    python main.py --port 8080
    python main.py --no-sim   # disable simulation, try real decoders only
"""

# eventlet.monkey_patch() MUST be the very first thing before any other imports
import eventlet
eventlet.monkey_patch()

import os
import sys
import json
import logging
import argparse

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
from decoders import DecoderManager

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config["SECRET_KEY"] = os.urandom(24)
app.config["TEMPLATES_AUTO_RELOAD"] = True

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="eventlet",
    logger=False,
    engineio_logger=False,
)

config = load_config()
decoder_manager = DecoderManager(config, socketio)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(decoder_manager.get_status())


@app.route("/api/config")
def api_config():
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_update_config():
    global config
    try:
        new_cfg = request.get_json(force=True)
        # Merge configuration
        for key, value in new_cfg.items():
            if key == "decoders":
                for dec_name, dec_cfg in value.items():
                    if dec_name in config.get("decoders", {}):
                        config["decoders"][dec_name].update(dec_cfg)
                    else:
                        config["decoders"][dec_name] = dec_cfg
            elif key == "simulation":
                config["simulation"].update(value)
            elif key == "map":
                config["map"].update(value)
            elif key == "rtl_sdr":
                config["rtl_sdr"].update(value)
            else:
                config[key] = value

        save_config(config)
        decoder_manager.update_config(config)
        return jsonify({"status": "ok", "config": config})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/decoder/<name>/start", methods=["POST"])
def api_start_decoder(name):
    ok = decoder_manager.start_decoder(name)
    return jsonify({"status": "ok" if ok else "error"})


@app.route("/api/decoder/<name>/stop", methods=["POST"])
def api_stop_decoder(name):
    ok = decoder_manager.stop_decoder(name)
    return jsonify({"status": "ok" if ok else "error"})


@app.route("/api/restart", methods=["POST"])
def api_restart():
    global config
    config = load_config()
    decoder_manager.stop_all()
    decoder_manager.__init__(config, socketio)  # reset
    decoder_manager.start_all()
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# SocketIO Events
# ---------------------------------------------------------------------------


@socketio.on("connect")
def handle_connect():
    logger.info(f"Client connected")
    emit("status", decoder_manager.get_status())


@socketio.on("disconnect")
def handle_disconnect():
    logger.info("Client disconnected")


@socketio.on("start_decoder")
def handle_start_decoder(data):
    name = data.get("name", "")
    decoder_manager.start_decoder(name)
    emit("status", decoder_manager.get_status())


@socketio.on("stop_decoder")
def handle_stop_decoder(data):
    name = data.get("name", "")
    decoder_manager.stop_decoder(name)
    emit("status", decoder_manager.get_status())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="RTL-SDR Multi-Protocol Monitor"
    )
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-sim", action="store_true",
                        help="Disable simulation mode (use real decoders)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.no_sim:
        config["simulation"]["enabled"] = False
        save_config(config)

    logger.info("Starting RTL-SDR Multi-Protocol Monitor...")
    logger.info(f"Simulation mode: {'ON' if config['simulation']['enabled'] else 'OFF'}")

    # Start decoder manager
    decoder_manager.start_all()

    # Print startup info
    log_lines = [
        "╔══════════════════════════════════════════════╗",
        "║     RTL-SDR Multi-Protocol Monitor          ║",
        "╠══════════════════════════════════════════════╣",
        f"║  Web UI:  http://{args.host}:{args.port:<5}               ║",
        f"║  Sim:     {'Enabled' if config['simulation']['enabled'] else 'Disabled':<20}          ║",
        "║  Protocols: ADS-B | ACARS | AIS | POCSAG   ║",
        "║             P2000 | ERMES                   ║",
        "╚══════════════════════════════════════════════╝",
    ]
    for line in log_lines:
        logger.info(line)

    try:
        socketio.run(
            app,
            host=args.host,
            port=args.port,
            debug=args.debug,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        pass
    finally:
        decoder_manager.stop_all()
        logger.info("Shutdown complete.")