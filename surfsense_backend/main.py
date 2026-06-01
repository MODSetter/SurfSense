import argparse
import asyncio
import logging
import sys

import uvicorn
from dotenv import load_dotenv

# Fix for Windows: psycopg requires SelectorEventLoop, not ProactorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.config.uvicorn import load_uvicorn_config

_old_log_record_factory = logging.getLogRecordFactory()


def _otel_safe_log_record_factory(*args, **kwargs):
    record = _old_log_record_factory(*args, **kwargs)
    if not hasattr(record, "otelTraceID"):
        record.otelTraceID = "0"
    if not hasattr(record, "otelSpanID"):
        record.otelSpanID = "0"
    return record


logging.setLogRecordFactory(_otel_safe_log_record_factory)

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(message)s"
    ),
    datefmt="%Y-%m-%d %H:%M:%S",
)

load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the SurfSense application")
    parser.add_argument("--reload", action="store_true", help="Enable hot reloading")
    args = parser.parse_args()

    config_kwargs = load_uvicorn_config(args)
    config = uvicorn.Config(**config_kwargs)
    server = uvicorn.Server(config)

    if sys.platform == "win32":
        asyncio.run(server.serve(), loop_factory=asyncio.SelectorEventLoop)
    else:
        server.run()
