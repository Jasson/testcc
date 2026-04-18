#!/usr/bin/env python3
"""Unit tests for server.py"""

import unittest
import json
import threading
import time
from http.client import HTTPConnection
from server import HTTPServer, Handler, HOST, PORT


class TestServerEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Start test server."""
        cls.server = HTTPServer((HOST, PORT), Handler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """Shutdown test server."""
        cls.server.shutdown()

    def test_health_endpoint(self):
        """Test /health endpoint returns 200 with ok status."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("GET", "/health")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(data["status"], "ok")
        conn.close()

    def test_status_endpoint(self):
        """Test /status endpoint returns 200 with status and version."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("GET", "/status")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(data["status"], "running")
        self.assertIn("version", data)
        conn.close()

    def test_not_found(self):
        """Test unknown endpoints return 404."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("GET", "/unknown")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 404)
        self.assertEqual(data["error"], "not found")
        conn.close()

    def test_post_data_endpoint(self):
        """Test POST /data endpoint."""
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"temperature": 25.5, "humidity": 60})
        conn.request("POST", "/data", payload)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertTrue(data.get("received"))
        conn.close()

    def test_post_invalid_json(self):
        """Test POST with invalid JSON returns 400."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("POST", "/data", "invalid json")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 400)
        self.assertEqual(data["error"], "invalid JSON")
        conn.close()


if __name__ == "__main__":
    unittest.main()
