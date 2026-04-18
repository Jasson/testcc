#!/usr/bin/env python3
"""Simple HTTP server for IoT data collection with JWT authentication."""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import jwt
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = 8080

USERS = {"admin": "password123"}
SECRET_KEY = "dev-secret-key"
TOKEN_EXPIRY = timedelta(hours=24)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

    def verify_token(self) -> bool:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False
        try:
            token = auth_header[7:]
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return True
        except jwt.InvalidTokenError:
            return False

    def send_json(self, code: int, data: dict):
        response = {"code": code, **data}
        body = json.dumps(response).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(200, {"status": "ok"})
        elif self.path == "/status":
            self.send_json(200, {"status": "running", "version": "1.0"})
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid JSON"})
            return

        if self.path == "/login":
            username = data.get("username")
            password = data.get("password")
            if username in USERS and USERS[username] == password:
                token = jwt.encode(
                    {"username": username, "exp": datetime.utcnow() + TOKEN_EXPIRY},
                    SECRET_KEY,
                    algorithm="HS256"
                )
                self.send_json(200, {"token": token})
            else:
                self.send_json(401, {"error": "invalid credentials"})
        elif self.path == "/data":
            if not self.verify_token():
                self.send_json(401, {"error": "unauthorized"})
                return
            logger.info("received: %s", data)
            self.send_json(200, {"received": True})
        else:
            self.send_json(404, {"error": "not found"})


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    logger.info("listening on %s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("stopped")
