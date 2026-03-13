"""
ServVia Pipeline Logging Middleware
====================================

Writes to both sys.__stdout__/stderr AND a log file to guarantee
visibility on Windows regardless of terminal buffering.
"""

import os
import sys
import time
from datetime import datetime

_TRACE_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline.log"
)


def _mw_write(msg: str):
    """Write a message to stdout, stderr, AND the pipeline log file."""
    try:
        sys.__stdout__.write(msg + "\n")
        sys.__stdout__.flush()
    except Exception:
        pass
    try:
        sys.__stderr__.write(msg + "\n")
        sys.__stderr__.flush()
    except Exception:
        pass
    try:
        with open(_TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


class PipelineLoggingMiddleware:
    """Logs every HTTP request/response with timing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.time()
        path = request.path
        method = request.method
        ts = datetime.now().strftime("%H:%M:%S")

        _mw_write(f"[{ts}] >>> {method} {path}")

        response = self.get_response(request)

        elapsed = time.time() - start
        status_code = response.status_code
        ts = datetime.now().strftime("%H:%M:%S")
        _mw_write(f"[{ts}] <<< {status_code} {path} ({elapsed:.1f}s)")

        return response
