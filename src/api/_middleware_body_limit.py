"""Request body size enforcement middleware."""

from __future__ import annotations

import json

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.core.constants import MAX_REQUEST_BODY_SIZE


class RequestBodyLimitMiddleware:
    """ASGI 中介層：串流計算請求體實際位元組數，超限時回傳 413。"""

    def __init__(self, app: ASGIApp, max_body_size: int = MAX_REQUEST_BODY_SIZE) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length_raw = headers.get(b"content-length")
        if content_length_raw is not None:
            try:
                if int(content_length_raw) <= self.max_body_size:
                    await self.app(scope, receive, send)
                    return
            except (ValueError, TypeError):
                pass

        bytes_received = 0
        body_exceeded = False

        async def limiting_receive() -> Message:
            nonlocal bytes_received, body_exceeded
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                bytes_received += len(chunk)
                if bytes_received > self.max_body_size:
                    body_exceeded = True
                    message["body"] = b""
                    message["more_body"] = False
            return message

        response_started = False

        async def limiting_send(message: Message) -> None:
            nonlocal response_started
            if body_exceeded and not response_started:
                if message["type"] == "http.response.start":
                    response_started = True
                    error_body = json.dumps(
                        {
                            "detail": (
                                f"請求體過大，上限為 {self.max_body_size // (1024 * 1024)} MB。"
                            ),
                        }
                    ).encode("utf-8")
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 413,
                            "headers": [
                                [b"content-type", b"application/json"],
                                [b"content-length", str(len(error_body)).encode()],
                            ],
                        }
                    )
                    await send({"type": "http.response.body", "body": error_body})
                    return
                if message["type"] == "http.response.body":
                    return
            await send(message)

        await self.app(scope, limiting_receive, limiting_send)
