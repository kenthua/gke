"""FastAPI entrypoint for packaging the ADK Agent as an Agent Substrate ActorTemplate.

Includes a lightweight local GCE Metadata Server bridge on 127.0.0.1:18080 so that
`google.auth.default()` (ADC) inside the hardware-isolated MicroVM works seamlessly
when the caller supplies a short-lived GCP access token via `POST /auth/token` (never
baking static credentials into the golden memory snapshot).
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import threading
from pydantic import BaseModel
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
ACTOR_SA_EMAIL = os.environ.get("ACTOR_SA_EMAIL", "default")
METADATA_PORT = 18080

# Point google-auth inside the MicroVM to our local metadata bridge
os.environ["GCE_METADATA_HOST"] = f"127.0.0.1:{METADATA_PORT}"
os.environ["GCE_METADATA_IP"] = f"127.0.0.1:{METADATA_PORT}"
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", PROJECT_ID)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

_TOKEN_STATE = {"access_token": "unconfigured", "expires_in": 5}


class _MetadataHandler(BaseHTTPRequestHandler):
    """Minimal GCE Metadata Server emulator for google.auth.default() inside MicroVM."""

    def log_message(self, fmt, *args):
        pass

    def _send(self, body: str, content_type: str = "text/plain"):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Metadata-Flavor", "Google")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.endswith("/project-id") or path.endswith("/numeric-project-id"):
            self._send(PROJECT_ID)
        elif path.endswith("/token"):
            self._send(
                json.dumps({
                    "access_token": _TOKEN_STATE["access_token"],
                    "expires_in": _TOKEN_STATE["expires_in"],
                    "token_type": "Bearer",
                }),
                content_type="application/json",
            )
        elif path.endswith("/email"):
            self._send(ACTOR_SA_EMAIL)
        elif path.endswith("/scopes"):
            self._send("https://www.googleapis.com/auth/cloud-platform\n")
        elif "service-accounts/default" in path:
            self._send(
                json.dumps({
                    "aliases": ["default"],
                    "email": ACTOR_SA_EMAIL,
                    "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
                }),
                content_type="application/json",
            )
        else:
            self._send("ok")


def _start_metadata_bridge():
    srv = HTTPServer(("127.0.0.1", METADATA_PORT), _MetadataHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()


_start_metadata_bridge()

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Expose standard ADK HTTP endpoints (/run, /run_sse, /apps/{app}/users/{user}/sessions, etc.)
app = get_fast_api_app(
    agents_dir=AGENTS_DIR,
    web=False,
)


class TokenPayload(BaseModel):
    access_token: str
    expires_in: int = 5


def set_access_token(payload: TokenPayload) -> dict:
    """Injects a short-lived GCP access token into the resumed MicroVM actor."""
    _TOKEN_STATE["access_token"] = payload.access_token
    _TOKEN_STATE["expires_in"] = payload.expires_in
    return {"status": "configured"}


def wakeup_probe() -> dict:
    """Used by Agent Substrate's wakeupProbe before taking the golden memory snapshot."""
    return {"status": "ready", "agent": "actor_resident_adk_agent"}


app.add_api_route("/auth/token", set_access_token, methods=["POST"])
app.add_api_route("/healthz", wakeup_probe, methods=["GET"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
