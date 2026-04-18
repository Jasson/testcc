#!/usr/bin/env python3
"""Unit tests for topic publishing functionality."""

import unittest
import json
import threading
import time
from http.client import HTTPConnection
from server import HTTPServer, Handler, HOST, PORT, SECRET_KEY, TOKEN_EXPIRY
import jwt
from datetime import datetime


class TestTopicEndpoints(unittest.TestCase):
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

    def _get_token(self, username="admin"):
        """Helper: Get valid JWT token."""
        return jwt.encode(
            {"username": username, "exp": datetime.utcnow() + TOKEN_EXPIRY},
            SECRET_KEY,
            algorithm="HS256"
        )

    def test_publish_topic_with_token(self):
        """Test POST /topics with valid token creates topic."""
        token = self._get_token()
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Test Topic", "content": "Test content"})
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("POST", "/topics", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 201)
        self.assertEqual(data["title"], "Test Topic")
        self.assertEqual(data["author"], "admin")
        self.assertIn("id", data)
        conn.close()

    def test_publish_topic_without_token(self):
        """Test POST /topics without token returns 401."""
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Test Topic", "content": "Test content"})
        conn.request("POST", "/topics", payload)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 401)
        self.assertEqual(data["error"], "unauthorized")
        conn.close()

    def test_publish_topic_missing_fields(self):
        """Test POST /topics with missing title/content returns 400."""
        token = self._get_token()
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Only title"})
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("POST", "/topics", payload, headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 400)
        self.assertEqual(data["error"], "title and content required")
        conn.close()

    def test_get_topics_with_token(self):
        """Test GET /topics with token returns topics list."""
        token = self._get_token()
        conn = HTTPConnection(HOST, PORT)
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("GET", "/topics", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertIn("topics", data)
        self.assertIn("total", data)
        self.assertIsInstance(data["topics"], list)
        conn.close()

    def test_get_topics_without_token(self):
        """Test GET /topics without token returns 401."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("GET", "/topics")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 401)
        self.assertEqual(data["error"], "unauthorized")
        conn.close()

    def test_get_single_topic(self):
        """Test GET /topics/:id returns specific topic."""
        token = self._get_token()

        # First, publish a topic
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Single Topic", "content": "Content"})
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("POST", "/topics", payload, headers)
        response = conn.getresponse()
        topic_data = json.loads(response.read())
        topic_id = topic_data["id"]
        conn.close()

        # Then, retrieve it
        conn = HTTPConnection(HOST, PORT)
        conn.request("GET", f"/topics/{topic_id}", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(data["id"], topic_id)
        self.assertEqual(data["title"], "Single Topic")
        conn.close()

    def test_get_nonexistent_topic(self):
        """Test GET /topics/:id with invalid ID returns 404."""
        token = self._get_token()
        conn = HTTPConnection(HOST, PORT)
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("GET", "/topics/invalid_id", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 404)
        self.assertEqual(data["error"], "topic not found")
        conn.close()

    def test_delete_topic_by_author(self):
        """Test DELETE /topics/:id by author succeeds."""
        token = self._get_token()

        # Publish a topic
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Delete Me", "content": "To be deleted"})
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("POST", "/topics", payload, headers)
        response = conn.getresponse()
        topic_data = json.loads(response.read())
        topic_id = topic_data["id"]
        conn.close()

        # Delete it
        conn = HTTPConnection(HOST, PORT)
        conn.request("DELETE", f"/topics/{topic_id}", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(data["message"], "deleted")
        conn.close()

    def test_delete_topic_by_other_user(self):
        """Test DELETE /topics/:id by non-author returns 403."""
        token1 = self._get_token("admin")

        # Publish as admin
        conn = HTTPConnection(HOST, PORT)
        payload = json.dumps({"title": "Admin Topic", "content": "Content"})
        headers = {"Authorization": f"Bearer {token1}"}
        conn.request("POST", "/topics", payload, headers)
        response = conn.getresponse()
        topic_data = json.loads(response.read())
        topic_id = topic_data["id"]
        conn.close()

        # Try to delete as different user
        token2 = jwt.encode(
            {"username": "other_user", "exp": datetime.utcnow() + TOKEN_EXPIRY},
            SECRET_KEY,
            algorithm="HS256"
        )
        conn = HTTPConnection(HOST, PORT)
        headers2 = {"Authorization": f"Bearer {token2}"}
        conn.request("DELETE", f"/topics/{topic_id}", headers=headers2)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 403)
        self.assertEqual(data["error"], "only author can delete")
        conn.close()

    def test_delete_nonexistent_topic(self):
        """Test DELETE /topics/:id with invalid ID returns 404."""
        token = self._get_token()
        conn = HTTPConnection(HOST, PORT)
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("DELETE", "/topics/invalid_id", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 404)
        self.assertEqual(data["error"], "topic not found")
        conn.close()

    def test_delete_without_token(self):
        """Test DELETE /topics/:id without token returns 401."""
        conn = HTTPConnection(HOST, PORT)
        conn.request("DELETE", "/topics/any_id")
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 401)
        self.assertEqual(data["error"], "unauthorized")
        conn.close()

    def test_topics_sorted_by_creation_time(self):
        """Test GET /topics returns topics sorted by creation time (newest first)."""
        token = self._get_token()

        # Publish multiple topics
        for i in range(3):
            conn = HTTPConnection(HOST, PORT)
            payload = json.dumps({"title": f"Topic {i}", "content": f"Content {i}"})
            headers = {"Authorization": f"Bearer {token}"}
            conn.request("POST", "/topics", payload, headers)
            conn.getresponse().read()
            conn.close()
            time.sleep(0.1)

        # Get topics
        conn = HTTPConnection(HOST, PORT)
        headers = {"Authorization": f"Bearer {token}"}
        conn.request("GET", "/topics", headers=headers)
        response = conn.getresponse()
        data = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertGreaterEqual(len(data["topics"]), 3)
        # Verify newest topic is first
        if len(data["topics"]) >= 2:
            self.assertGreater(data["topics"][0]["created_at"], data["topics"][-1]["created_at"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
