import asyncio
import json
import random
import time
import urllib.request
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import websockets

WS_HOST = "localhost"
WS_PORT = 8765
HTTP_HOST = "localhost"
HTTP_PORT = 8000
SEND_COMMAND_URL = None

class WebServer:
    def __init__(self):
        self.clients = set()
        self.clients_lock = threading.Lock()
        self.loop = None
        self.start_time = time.time()
        self.command_state = {
            "laser": False,
            "fire": False,
            "stepper": 0,
            "servo": 90,
        }
        self.telemetry = {
            "temp": 28.0,
            "load": 12,
            "uptime": "0s",
            "rot": 0,
            "fps": 0.0,
        }
        self.telemetry_overrides = set()

    async def handler(self, websocket, path=None):
        with self.clients_lock:
            self.clients.add(websocket)
        print("Client connected.", "path=" + str(path))
        try:
            await self.command_receiver(websocket)
        finally:
            with self.clients_lock:
                self.clients.discard(websocket)
            print("Client disconnected.")

    async def command_receiver(self, websocket):
        async for message in websocket:
            try:
                data = json.loads(message)
                self.apply_command(data)
            except json.JSONDecodeError:
                print("Received invalid JSON from client:", message)

    async def broadcast_message(self, message):
        with self.clients_lock:
            clients = list(self.clients)
        if not clients:
            return
        results = await asyncio.gather(*(client.send(message) for client in clients), return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                print(f"Broadcast error: {result}")

    def send_json_to_clients(self, payload):
        self.apply_external_data(payload)
        if self.loop is None:
            print("Cannot broadcast, websocket loop is not yet initialized")
            return
        try:
            message = json.dumps(payload)
        except Exception as exc:
            print(f"Failed to serialize payload: {exc}")
            return
        asyncio.run_coroutine_threadsafe(self.broadcast_message(message), self.loop)

    def apply_external_data(self, data):
        telemetry_fields = {"temp", "load", "uptime", "rot", "fps"}
        for key in telemetry_fields:
            if key in data:
                self.telemetry[key] = data[key]
                self.telemetry_overrides.add(key)

    def apply_command(self, data):
        if "laser" in data:
            self.command_state["laser"] = bool(data["laser"])
        if "fire" in data:
            self.command_state["fire"] = bool(data["fire"])
        if "stepper" in data:
            self.command_state["stepper"] = int(data["stepper"])
        if "servo" in data:
            self.command_state["servo"] = int(data["servo"])
        print("Command received:", json.dumps(self.command_state))
        self.send_command_json()

    async def telemetry_sender(self, websocket):
        while True:
            self.update_telemetry()
            payload = json.dumps(self.telemetry)
            await websocket.send(payload)
            await asyncio.sleep(0.15)

    def send_command_json(self):
        payload = json.dumps(self.command_state).encode("utf-8")
        if SEND_COMMAND_URL:
            try:
                req = urllib.request.Request(
                    SEND_COMMAND_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    print(f"Forwarded command JSON to {SEND_COMMAND_URL}; status={resp.status}")
            except Exception as exc:
                print(f"Failed to forward command JSON: {exc}")
        else:
            print("Command JSON ready:", json.dumps(self.command_state))

    def update_telemetry(self):
        uptime_seconds = int(time.time() - self.start_time)
        if "uptime" not in self.telemetry_overrides:
            self.telemetry["uptime"] = f"{uptime_seconds}s"
        if "temp" not in self.telemetry_overrides:
            self.telemetry["temp"] = round(26.0 + random.random() * 4.0, 1)
        if "load" not in self.telemetry_overrides:
            self.telemetry["load"] = min(100, max(0, int(12 + random.randint(-3, 3) + self.command_state["fire"] * 15)))

        if "rot" not in self.telemetry_overrides:
            self.telemetry["rot"] = self.command_state["servo"] if self.command_state["stepper"] == 0 else \
                max(0, min(180, self.telemetry["rot"] + self.command_state["stepper"] * 2))

        if "fps" not in self.telemetry_overrides:
            self.telemetry["fps"] = round(20.0 + random.random() * 12.0, 1)

    def run_http_server(self):
        class StatusHandler(BaseHTTPRequestHandler):
            def do_GET(self_inner):
                if self_inner.path not in ("/", "/status"):
                    self_inner.send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return

                body = self.build_status_page().encode("utf-8")
                self_inner.send_response(HTTPStatus.OK)
                self_inner.send_header("Content-Type", "text/html; charset=utf-8")
                self_inner.send_header("Content-Length", str(len(body)))
                self_inner.end_headers()
                self_inner.wfile.write(body)

            def do_POST(self_inner):
                if self_inner.path != "/send":
                    self_inner.send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return

                length = int(self_inner.headers.get("Content-Length", 0))
                body = self_inner.rfile.read(length)
                try:
                    data = json.loads(body.decode("utf-8"))
                except Exception as exc:
                    self_inner.send_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
                    return

                self_inner.server.owner.send_json_to_clients(data)
                response = json.dumps({"sent": True}).encode("utf-8")
                self_inner.send_response(HTTPStatus.OK)
                self_inner.send_header("Content-Type", "application/json")
                self_inner.send_header("Content-Length", str(len(response)))
                self_inner.end_headers()
                self_inner.wfile.write(response)

            def log_message(self_inner, format, *args):
                return

        server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), StatusHandler)
        server.owner = self
        print(f"HTTP status page available at http://{HTTP_HOST}:{HTTP_PORT}")
        print(f"HTTP send endpoint available at http://{HTTP_HOST}:{HTTP_PORT}/send")
        server.serve_forever()

    def build_status_page(self):
        return f"""
<html>
<head>
    <meta charset='utf-8'>
    <title>Web Server Status</title>
    <style>
        body {{ background:#0b1220; color:#d8e6f3; font-family:Segoe UI, sans-serif; padding:24px; }}
        .card {{ background:#141c2d; border:1px solid #1f2a3d; border-radius:12px; padding:18px; margin-bottom:16px; }}
        h1 {{ color:#2ae1ff; }}
        dt {{ font-weight:700; }}
    </style>
</head>
<body>
    <h1>Web Server</h1>
    <div class='card'>
        <dl>
            <dt>WebSocket Endpoint</dt>
            <dd>ws://{WS_HOST}:{WS_PORT}</dd>
            <dt>Connected Clients</dt>
            <dd>{len(self.clients)}</dd>
            <dt>Last Command</dt>
            <dd><pre>{json.dumps(self.command_state, indent=2)}</pre></dd>
            <dt>Last Telemetry</dt>
            <dd><pre>{json.dumps(self.telemetry, indent=2)}</pre></dd>
        </dl>
    </div>
    <p>Reload this page to refresh the server status.</p>
</body>
</html>
"""

    async def run_ws_server(self):
        self.loop = asyncio.get_running_loop()
        print(f"WebSocket server listening on ws://{WS_HOST}:{WS_PORT}")
        async with websockets.serve(self.handler, WS_HOST, WS_PORT):
            await asyncio.Future()

    def run(self):
        Thread(target=self.run_http_server, daemon=True).start()
        asyncio.run(self.run_ws_server())


SERVER_INSTANCE = None

def send_json_to_control_panel(payload):
    """Send JSON to all connected control panel websocket clients."""
    if SERVER_INSTANCE is None:
        raise RuntimeError("Server instance is not running")
    SERVER_INSTANCE.send_json_to_clients(payload)


if __name__ == "__main__":
    SERVER_INSTANCE = WebServer()
    SERVER_INSTANCE.run()
