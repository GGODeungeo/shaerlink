"""Runs on the static-IP relay droplet only - accepts a tacaItemId from our
Vercel function (which can't call sharelink directly, since sharelink's Open
API enforces a source-IP allowlist that Vercel's dynamic egress IP fails),
issues the link from here instead, and returns the result.

ponytail: plain HTTP, not HTTPS - this is a server-to-server call between
Vercel and this droplet (never touched by a browser), gated by RELAY_TOKEN.
Add TLS if that stops being true.
"""
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from sharelink_api import get_access_token, issue_link_with_origin

RELAY_TOKEN = os.environ["RELAY_TOKEN"]
PUBLISHER_ID = os.environ["SHARELINK_PUBLISHER_ID"]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get("x-relay-token") != RELAY_TOKEN:
            self._respond(401, {"error": "unauthorized"})
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            taca_item_id = int(body["tacaItemId"])
        except (json.JSONDecodeError, KeyError, ValueError):
            self._respond(400, {"error": "tacaItemId is required"})
            return

        try:
            token = get_access_token()
            link = issue_link_with_origin(token, taca_item_id, PUBLISHER_ID)
        except Exception as e:
            self._respond(502, {"error": str(e)})
            return

        self._respond(200, link)

    def _respond(self, status: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
