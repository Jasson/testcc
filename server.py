#!/usr/bin/env python3
"""Simple HTTP server for IoT data collection with JWT authentication and topic publishing."""

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import jwt
from datetime import datetime, timedelta
import uuid
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HOST = "0.0.0.0"
PORT = 8080

USERS = {"admin": "password123"}
SECRET_KEY = "dev-secret-key"
TOKEN_EXPIRY = timedelta(hours=24)

topics_store = {}
topic_counter = 0


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

    def get_current_user(self) -> str:
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        try:
            token = auth_header[7:]
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return payload.get("username")
        except jwt.InvalidTokenError:
            return None

    def send_json(self, code: int, data: dict):
        response = {"code": code, **data}
        body = json.dumps(response).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html_file = os.path.join(SCRIPT_DIR, "web", "index.html")
            try:
                with open(html_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(content))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_json(404, {"error": "not found"})
        elif self.path == "/health":
            self.send_json(200, {"status": "ok"})
        elif self.path == "/status":
            self.send_json(200, {"status": "running", "version": "1.0"})
        elif self.path == "/topics":
            if not self.verify_token():
                self.send_json(401, {"error": "unauthorized"})
                return
            topics = sorted(topics_store.values(), key=lambda x: x["created_at"], reverse=True)
            self.send_json(200, {"topics": topics, "total": len(topics)})
        elif self.path.startswith("/topics/"):
            if not self.verify_token():
                self.send_json(401, {"error": "unauthorized"})
                return
            topic_id = self.path[8:]
            if topic_id in topics_store:
                self.send_json(200, topics_store[topic_id])
            else:
                self.send_json(404, {"error": "topic not found"})
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
        elif self.path == "/topics":
            if not self.verify_token():
                self.send_json(401, {"error": "unauthorized"})
                return
            username = self.get_current_user()
            title = data.get("title", "").strip()
            content = data.get("content", "").strip()
            if not title or not content:
                self.send_json(400, {"error": "title and content required"})
                return
            global topic_counter
            topic_counter += 1
            topic_id = f"topic_{topic_counter}"
            now = datetime.utcnow().isoformat() + "Z"
            topic = {
                "id": topic_id,
                "title": title,
                "content": content,
                "author": username,
                "created_at": now,
                "updated_at": now
            }
            topics_store[topic_id] = topic
            logger.info("topic created: %s by %s", topic_id, username)
            self.send_json(201, topic)
        else:
            self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        if self.path.startswith("/topics/"):
            if not self.verify_token():
                self.send_json(401, {"error": "unauthorized"})
                return
            topic_id = self.path[8:]
            username = self.get_current_user()
            if topic_id not in topics_store:
                self.send_json(404, {"error": "topic not found"})
                return
            if topics_store[topic_id]["author"] != username:
                self.send_json(403, {"error": "only author can delete"})
                return
            del topics_store[topic_id]
            logger.info("topic deleted: %s by %s", topic_id, username)
            self.send_json(200, {"message": "deleted"})
        else:
            self.send_json(404, {"error": "not found"})


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    logger.info("listening on %s:%d", HOST, PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("stopped")
