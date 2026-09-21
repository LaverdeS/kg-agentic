# ruff: noqa: E501
"""Small stdlib HTTP/SSE API for the optional local graph explorer."""

from __future__ import annotations

import asyncio
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

from kg_agentic.application.cement import CORPUS_ID
from kg_agentic.infrastructure.bootstrap import investigate_cement_slice
from kg_agentic.infrastructure.runtime import Settings
from kg_agentic.knowledge.models import InvestigationRequest
from local_experience.api.recorded import recorded_result
from local_experience.api.scene import project_scene, scene_payload

HOST = "127.0.0.1"
PORT = 8000
CLIENT_DIST = Path(__file__).parents[1] / "client" / "dist"


class ExplorerHandler(BaseHTTPRequestHandler):
    server_version = "kg-agentic-local-experience/0.1"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._respond(HTTPStatus.NO_CONTENT, None)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._respond(HTTPStatus.OK, {"status": "ready", "corpus": CORPUS_ID})
            return
        if self.path == "/api/scene/recorded":
            self._respond(HTTPStatus.OK, _recorded_payload())
            return
        if self.path.startswith("/api/"):
            self._respond(HTTPStatus.NOT_FOUND, {"error": "No local-experience endpoint at this path."})
            return
        self._serve_client()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/investigations":
            self._respond(
                HTTPStatus.NOT_FOUND, {"error": "No local-experience endpoint at this path."}
            )
            return
        try:
            request = self._read_json()
            mode = request.get("mode", "recorded")
            question = request.get("question", "")
            if not isinstance(mode, str) or mode not in {"recorded", "live"}:
                raise ValueError("mode must be either 'recorded' or 'live'")
            if not isinstance(question, str):
                raise ValueError("question must be a string")
        except ValueError as error:
            self._respond(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        self._stream_investigation(mode=mode, question=question)

    def _stream_investigation(self, *, mode: str, question: str) -> None:
        self.send_response(HTTPStatus.OK)
        self._headers("text/event-stream")
        self.end_headers()
        self._event("run_started", {"mode": mode, "message": "Preparing investigation scene."})
        try:
            if mode == "recorded":
                payload = _recorded_payload(question=question)
                for trace in cast(list[dict[str, object]], payload["trace"]):
                    self._event("activity", trace)
                self._event("graph_delta", {"nodes": payload["nodes"], "edges": payload["edges"]})
                self._event("completed", payload)
                return
            self._event(
                "activity",
                {"action": "retrieve", "detail": "Calling the core investigation use case."},
            )
            payload = _live_payload(question)
            self._event("graph_delta", {"nodes": payload["nodes"], "edges": payload["edges"]})
            self._event("completed", payload)
        except (
            Exception
        ) as error:  # Surface a real service failure; never replace it with demo data.
            self._event("failed", {"message": str(error), "errorType": type(error).__name__})

    def _event(self, event: str, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        self.wfile.write(f"event: {event}\ndata: {encoded}\n\n".encode())
        self.wfile.flush()

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as error:
            raise ValueError("Request body must be valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _respond(self, status: HTTPStatus, payload: dict[str, object] | None) -> None:
        self.send_response(status)
        self._headers("application/json")
        self.end_headers()
        if payload is not None:
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode())

    def _serve_client(self) -> None:
        relative_path = self.path.split("?", maxsplit=1)[0].lstrip("/") or "index.html"
        requested = (CLIENT_DIST / relative_path).resolve()
        try:
            requested.relative_to(CLIENT_DIST.resolve())
        except ValueError:
            self._respond(HTTPStatus.NOT_FOUND, {"error": "Unknown client asset."})
            return
        if not requested.is_file():
            requested = CLIENT_DIST / "index.html"
        if not requested.is_file():
            self._respond(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"error": "Build the local client first with `npm run ui:build`."},
            )
            return
        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self._headers(content_type)
        self.end_headers()
        self.wfile.write(requested.read_bytes())

    def _headers(self, content_type: str) -> None:
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Cache-Control", "no-store")

    def log_message(self, format: str, *args: object) -> None:
        """Keep browser polling and streaming noise out of the terminal."""


def _recorded_payload(question: str = "") -> dict[str, object]:
    scene = project_scene(recorded_result(), mode="recorded")
    payload = scene_payload(scene)
    if question.strip():
        payload["question"] = question.strip()
    return payload


def _live_payload(question: str) -> dict[str, object]:
    if not question.strip():
        raise ValueError("A live investigation needs a question.")
    load_dotenv()
    settings = Settings.from_environment()
    result, usage = asyncio.run(
        investigate_cement_slice(settings, InvestigationRequest(question=question.strip()))
    )
    payload = scene_payload(project_scene(result, mode="live"))
    payload["usage"] = usage
    return payload


def main() -> None:
    print(f"Local experience API: http://{HOST}:{PORT}/api/health")
    ThreadingHTTPServer((HOST, PORT), ExplorerHandler).serve_forever()


if __name__ == "__main__":
    main()
