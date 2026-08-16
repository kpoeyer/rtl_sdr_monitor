#!/usr/bin/env python3
"""
RTL-SDR Decoder Manager
Manages subprocesses for various SDR-based radio decoders.
"""

import os
import re
import json
import time
import signal
import subprocess
import threading
import logging
from datetime import datetime, timezone
from queue import Queue
from random import uniform, randint, choice

logger = logging.getLogger(__name__)


# =============================================================================
# Simulated data generators (for testing without hardware)
# =============================================================================

class Simulator:
    """Generates simulated decoded messages for testing."""

    AIRCRAFT = [
        {"callsign": "KLM123", "flight": "KL123", "altitude": 35000,
         "speed": 450, "heading": 275, "squawk": "5732"},
        {"callsign": "EZY456", "flight": "U2456", "altitude": 31000,
         "speed": 420, "heading": 180, "squawk": "4321"},
        {"callsign": "BAW789", "flight": "BA789", "altitude": 37000,
         "speed": 480, "heading": 90, "squawk": "6512"},
        {"callsign": "DLH101", "flight": "LH101", "altitude": 33000,
         "speed": 440, "heading": 45, "squawk": "3421"},
        {"callsign": "AFR222", "flight": "AF222", "altitude": 29000,
         "speed": 400, "heading": 135, "squawk": "2345"},
    ]

    SHIPS = [
        {"name": "MSC LORETTA", "mmsi": 636092000, "speed": 18.5,
         "heading": 45, "destination": "ROTTERDAM"},
        {"name": "MAERSK EINDHOVEN", "mmsi": 219030000, "speed": 12.3,
         "heading": 270, "destination": "ANTWERP"},
        {"name": "COSCO SHIPPING TURKEY", "mmsi": 477712800, "speed": 15.0,
         "heading": 315, "destination": "HAMBURG"},
        {"name": "EVER GIVEN", "mmsi": 353136000, "speed": 0.1,
         "heading": 90, "destination": "ROTTERDAM"},
        {"name": "CMA CGM LOUIS BLERIOT", "mmsi": 229210000, "speed": 20.1,
         "heading": 180, "destination": "LE HAVRE"},
    ]

    # Dutch cities for P2000 incidents
    NL_CITIES = [
        {"name": "Rotterdam", "lat": 51.9244, "lon": 4.4777},
        {"name": "Amsterdam", "lat": 52.3676, "lon": 4.9041},
        {"name": "Den Haag", "lat": 52.0705, "lon": 4.3007},
        {"name": "Utrecht", "lat": 52.0907, "lon": 5.1214},
        {"name": "Eindhoven", "lat": 51.4416, "lon": 5.4697},
        {"name": "Fijnaart", "lat": 51.6361, "lon": 4.4708},
        {"name": "Breda", "lat": 51.5719, "lon": 4.7683},
        {"name": "Tilburg", "lat": 51.5591, "lon": 5.0920},
    ]

    P2000_CODES = [
        {"code": "PRIO 1", "service": "Brandweer", "description": "BRAND WONING"},
        {"code": "PRIO 2", "service": "Ambulance", "description": "AMI - Hartproblemen"},
        {"code": "PRIO 1", "service": "Politie", "description": "Overval alarm"},
        {"code": "PRIO 2", "service": "Brandweer", "description": "BRAND BUITEN"},
        {"code": "PRIO 1", "service": "Ambulance", "description": "A1 - Reanimatie"},
    ]

    POCSAG_TYPES = ["numeric", "alpha", "numeric", "alpha", "alpha"]
    POCSAG_MSGS = [
        "Bel 06-12345678 dringend",
        "Reminder: vergadering 14:00",
        "Klant wacht op terugbel",
        "Medicatie gereed voor ophalen",
        "Service oproep - locatie 42B",
        "Parkeervergunning verlopen - bel gemeente",
    ]

    ACARS_MSGS = [
        "WIND 240/45KT TEMP -52C",
        "ETA 1432Z FUEL REM 5.2T",
        "REQ GATE ASSIGNMENT",
        "MAINTENANCE REQ: FLAPS ACTUATOR",
        "POSITION REPORT: N5100 W00123",
        "WEATHER: CB TOPS FL380",
        "FUEL REQ 12.5T FOR NEXT SECTOR",
    ]

    ERMES_MSGS = [
        "Pagina: 0123456789 Bericht: Bel kantoor",
        "Bericht: Onderhoud gepland 03:00-05:00",
        "Alarm: Temperatuur sensor 7B te hoog",
        "Melding: Serverroom deur open",
        "Service: UPS test gepland",
    ]

    def __init__(self):
        self._running = False
        self._thread = None
        self._queue = None
        self._aircraft_positions = {}
        self._ship_positions = {}

    def start(self, queue):
        self._running = True
        self._queue = queue
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("Simulator started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Simulator stopped")

    def _run(self):
        """Main simulation loop."""
        # Initialize some aircraft and ship positions
        for i, ac in enumerate(self.AIRCRAFT):
            self._aircraft_positions[ac["callsign"]] = {
                "lat": 51.5 + uniform(-1, 1),
                "lon": 4.0 + uniform(-1, 1),
                "altitude": ac["altitude"],
                "heading": ac["heading"],
                "speed": ac["speed"],
            }

        for i, ship in enumerate(self.SHIPS):
            self._ship_positions[ship["name"]] = {
                "lat": 51.8 + uniform(-0.5, 0.5),
                "lon": 3.8 + uniform(-0.5, 0.5),
                "heading": ship["heading"],
                "speed": ship["speed"],
            }

        cycle = 0
        while self._running and self._queue is not None:
            try:
                self._generate_adsb(cycle)
                self._generate_ais(cycle)
                self._generate_acars(cycle)
                self._generate_pocsag(cycle)
                self._generate_p2000(cycle)
                self._generate_ermes(cycle)
                cycle += 1
                time.sleep(3)
            except Exception as e:
                logger.error(f"Simulator error: {e}")

    def _generate_adsb(self, cycle):
        for callsign, pos in self._aircraft_positions.items():
            if cycle % 3 != hash(callsign) % 3:
                continue
            pos["lat"] += uniform(-0.05, 0.05)
            pos["lon"] += uniform(-0.05, 0.05)
            pos["altitude"] += uniform(-500, 500)
            pos["heading"] = (pos["heading"] + uniform(-5, 5)) % 360
            pos["speed"] += uniform(-10, 10)

            msg = {
                "type": "adsb",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "callsign": callsign,
                    "altitude": int(pos["altitude"]),
                    "speed": int(pos["speed"]),
                    "heading": int(pos["heading"]),
                    "lat": round(pos["lat"], 5),
                    "lon": round(pos["lon"], 5),
                    "track_id": f"AC-{randint(10000, 99999)}",
                }
            }
            self._queue.put(msg)

    def _generate_ais(self, cycle):
        for name, pos in self._ship_positions.items():
            if cycle % 2 != hash(name) % 2:
                continue
            pos["lat"] += uniform(-0.01, 0.01)
            pos["lon"] += uniform(-0.01, 0.01)
            pos["speed"] += uniform(-0.5, 0.5)

            ship = next(s for s in self.SHIPS if s["name"] == name)
            msg = {
                "type": "ais",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "name": name,
                    "mmsi": ship["mmsi"],
                    "speed": round(pos["speed"], 1),
                    "heading": pos["heading"],
                    "lat": round(pos["lat"], 5),
                    "lon": round(pos["lon"], 5),
                    "destination": ship["destination"],
                }
            }
            self._queue.put(msg)

    def _generate_acars(self, cycle):
        if cycle % 2 != 0:
            return
        lat = 51.5 + uniform(-2, 2)
        lon = 4.5 + uniform(-2, 2)
        msg_text = choice(self.ACARS_MSGS)
        ac = choice(self.AIRCRAFT)

        msg = {
            "type": "acars",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "aircraft": ac["callsign"],
                "flight": ac["flight"],
                "text": msg_text,
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "frequency": choice([131550, 131725, 130025]),
            }
        }
        self._queue.put(msg)

    def _generate_pocsag(self, cycle):
        if cycle % 4 != 0:
            return
        msg_type = choice(self.POCSAG_TYPES)
        msg = {
            "type": "pocsag",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "type": msg_type,
                "message": choice(self.POCSAG_MSGS),
                "address": randint(1000000, 9999999),
                "function": randint(0, 3),
                "frequency": 169650,
            }
        }
        self._queue.put(msg)

    def _generate_p2000(self, cycle):
        if cycle % 5 != 0:
            return
        city = choice(self.NL_CITIES)
        incident = choice(self.P2000_CODES)
        capcodes = f"{randint(1000, 9999)}-{randint(1000, 9999)}-{randint(100, 999)}"

        msg = {
            "type": "p2000",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "capcode": capcodes,
                "code": incident["code"],
                "service": incident["service"],
                "description": incident["description"],
                "location": city["name"],
                "lat": round(city["lat"] + uniform(-0.01, 0.01), 5),
                "lon": round(city["lon"] + uniform(-0.01, 0.01), 5),
                "frequency": 169650,
            }
        }
        self._queue.put(msg)

    def _generate_ermes(self, cycle):
        if cycle % 6 != 0:
            return
        msg = {
            "type": "ermes",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "message": choice(self.ERMES_MSGS),
                "frequency": 169450,
            }
        }
        self._queue.put(msg)


# =============================================================================
# Real Decoder Process Management
# =============================================================================

class DecoderProcess:
    """Manages a single decoder subprocess."""

    def __init__(self, name, command, args=None, pipe_to=None, frequency=None):
        self.name = name
        self.command = command
        self.args = args or []
        self.pipe_to = pipe_to  # [cmd, arg1, arg2, ...] for piped decoder
        self.frequency = frequency
        self._process = None
        self._pipe_process = None
        self._running = False
        self._thread = None
        self._queue = None

    def start(self, queue):
        """Start the decoder subprocess."""
        if self._running:
            return False

        self._queue = queue
        self._running = True

        # Build the command
        cmd = [self.command] + self.args
        if self.frequency:
            # Insert frequency if not already in args
            freq_args = []
            for a in cmd:
                if a.startswith('-f'):
                    break
            else:
                # Check if format needs frequency
                if self.command in ('rtl_fm',):
                    cmd = [self.command, '-f', str(self.frequency)] + self.args

        logger.info(f"Starting decoder: {self.name} -> {' '.join(cmd)}")

        try:
            if self.pipe_to:
                # rtl_fm | decoder format
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN)
                )
                self._pipe_process = subprocess.Popen(
                    self.pipe_to,
                    stdin=self._process.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN)
                )
                if self._process.stdout:
                    self._process.stdout.close()  # Allow pipe_process to receive SIGPIPE
                self._thread = threading.Thread(
                    target=self._read_pipe_output,
                    args=(self._pipe_process,),
                    daemon=True
                )
            else:
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN)
                )
                self._thread = threading.Thread(
                    target=self._read_output,
                    args=(self._process,),
                    daemon=True
                )

            self._thread.start()
            return True

        except FileNotFoundError:
            logger.warning(f"Command not found for {self.name}: {self.command}")
            self._running = False
            return False
        except Exception as e:
            logger.error(f"Error starting {self.name}: {e}")
            self._running = False
            return False

    def _read_output(self, process):
        """Read stdout line by line from the process."""
        try:
            for line in iter(process.stdout.readline, b''):
                if not self._running:
                    break
                line = line.decode('utf-8', errors='replace').strip()
                if line:
                    self._parse_and_queue(line)
        except Exception as e:
            logger.error(f"Error reading {self.name} output: {e}")

    def _read_pipe_output(self, pipe_process):
        """Read stdout from the piped decoder."""
        try:
            for line in iter(pipe_process.stdout.readline, b''):
                if not self._running:
                    break
                line = line.decode('utf-8', errors='replace').strip()
                if line:
                    self._parse_and_queue(line)
        except Exception as e:
            logger.error(f"Error reading {self.name} pipe output: {e}")

    def _parse_and_queue(self, line):
        """Parse a raw line and queue a structured message."""
        # This is a basic parser; real implementations would be decoder-specific
        msg = {
            "type": self.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "raw": line,
            "data": {"text": line},
        }
        if self._queue:
            self._queue.put(msg)

    def stop(self):
        """Stop the decoder process."""
        self._running = False

        for proc in [self._pipe_process, self._process]:
            if proc:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                except Exception:
                    pass

        self._process = None
        self._pipe_process = None
        logger.info(f"Decoder stopped: {self.name}")

    @property
    def is_running(self):
        if self._process:
            return self._process.poll() is None
        return self._running


# =============================================================================
# Decoder Manager
# =============================================================================

class DecoderManager:
    """Manages all decoder processes and the simulator."""

    def __init__(self, config, socketio=None):
        self.config = config
        self.socketio = socketio
        self._queue = Queue()
        self._decoders = {}
        self._simulator = Simulator()
        self._running = False
        self._emitter_thread = None

        # Initialize decoders from config
        self._init_decoders()

    def _init_decoders(self):
        """Create decoder process objects from configuration."""
        dec_cfg = self.config.get("decoders", {})

        for name, cfg in dec_cfg.items():
            if not cfg.get("enabled", True):
                continue

            decoder = DecoderProcess(
                name=name,
                command=cfg.get("command", ""),
                args=cfg.get("args", []),
                pipe_to=cfg.get("pipe_to"),
                frequency=cfg.get("frequency"),
            )
            self._decoders[name] = decoder

    def start_all(self):
        """Start all decoders (or simulator)."""
        self._running = True

        # Start the queue emitter
        self._emitter_thread = threading.Thread(target=self._emit_loop, daemon=True)
        self._emitter_thread.start()

        sim_enabled = self.config.get("simulation", {}).get("enabled", True)

        if sim_enabled:
            logger.info("Starting simulator")
            self._simulator.start(self._queue)
        else:
            for name, decoder in self._decoders.items():
                if decoder.start(self._queue):
                    logger.info(f"Started decoder: {name}")
                else:
                    # Fall back to simulator for this decoder type
                    logger.info(f"Using simulated data for: {name}")

        return True

    def start_decoder(self, name):
        """Start a specific decoder."""
        if name in self._decoders:
            return self._decoders[name].start(self._queue)
        return False

    def stop_decoder(self, name):
        """Stop a specific decoder."""
        if name in self._decoders:
            self._decoders[name].stop()
            return True
        return False

    def stop_all(self):
        """Stop all decoders and simulator."""
        self._running = False
        self._simulator.stop()
        for decoder in self._decoders.values():
            decoder.stop()
        if self._emitter_thread:
            self._emitter_thread.join(timeout=3)

    def get_status(self):
        """Get status of all decoders."""
        sim_enabled = self.config.get("simulation", {}).get("enabled", True)
        status = {
            "simulator": {
                "running": self._simulator._running if sim_enabled else False,
                "enabled": sim_enabled,
            }
        }
        for name, decoder in self._decoders.items():
            status[name] = {
                "running": decoder.is_running,
                "frequency": decoder.frequency,
                "configured": True,
            }
        return status

    def _emit_loop(self):
        """Continuously emit queued messages via SocketIO."""
        while self._running:
            try:
                msg = self._queue.get(timeout=1)
                if msg and self.socketio:
                    self.socketio.emit("message", msg, namespace="/")
            except Exception:
                continue

    def update_config(self, new_config):
        """Update configuration and restart affected decoders."""
        self.config.update(new_config)
        self.stop_all()
        self._init_decoders()
        self.start_all()