import uvicorn
import argparse
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

load_dotenv()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run the SurfSense application')
    parser.add_argument('--reload', action='store_true', help='Enable hot reloading')
    args = parser.parse_args()

    config_kwargs = dict(
        app="app.app:app",
        host=os.getenv("UVICORN_HOST", "0.0.0.0"),
        port=int(os.getenv("UVICORN_PORT", 8000)),
        log_level=os.getenv("UVICORN_LOG_LEVEL", "info"),
        reload=args.reload,
        reload_dirs=["app"] if args.reload else None,
    )

    # Only add advanced args if set in env
    if os.getenv("UVICORN_PROXY_HEADERS"):
        config_kwargs["proxy_headers"] = (
            os.getenv("UVICORN_PROXY_HEADERS").lower() == "true"
        )
    if os.getenv("UVICORN_FORWARDED_ALLOW_IPS"):
        config_kwargs["forwarded_allow_ips"] = os.getenv("UVICORN_FORWARDED_ALLOW_IPS")
    if os.getenv("UVICORN_WORKERS"):
        config_kwargs["workers"] = int(os.getenv("UVICORN_WORKERS"))
    if os.getenv("UVICORN_ACCESS_LOG"):
        config_kwargs["access_log"] = os.getenv("UVICORN_ACCESS_LOG").lower() == "true"
    if os.getenv("UVICORN_LOOP"):
        config_kwargs["loop"] = os.getenv("UVICORN_LOOP")
    if os.getenv("UVICORN_HTTP"):
        config_kwargs["http"] = os.getenv("UVICORN_HTTP")
    if os.getenv("UVICORN_WS"):
        config_kwargs["ws"] = os.getenv("UVICORN_WS")
    if os.getenv("UVICORN_LIFESPAN"):
        config_kwargs["lifespan"] = os.getenv("UVICORN_LIFESPAN")
    if os.getenv("UVICORN_ENV_FILE"):
        config_kwargs["env_file"] = os.getenv("UVICORN_ENV_FILE")
    if os.getenv("UVICORN_LOG_CONFIG"):
        config_kwargs["log_config"] = os.getenv("UVICORN_LOG_CONFIG")
    if os.getenv("UVICORN_SERVER_HEADER"):
        config_kwargs["server_header"] = (
            os.getenv("UVICORN_SERVER_HEADER").lower() == "true"
        )
    if os.getenv("UVICORN_DATE_HEADER"):
        config_kwargs["date_header"] = (
            os.getenv("UVICORN_DATE_HEADER").lower() == "true"
        )
    if os.getenv("UVICORN_LIMIT_CONCURRENCY"):
        config_kwargs["limit_concurrency"] = int(os.getenv("UVICORN_LIMIT_CONCURRENCY"))
    if os.getenv("UVICORN_LIMIT_MAX_REQUESTS"):
        config_kwargs["limit_max_requests"] = int(
            os.getenv("UVICORN_LIMIT_MAX_REQUESTS")
        )
    if os.getenv("UVICORN_TIMEOUT_KEEP_ALIVE"):
        config_kwargs["timeout_keep_alive"] = int(
            os.getenv("UVICORN_TIMEOUT_KEEP_ALIVE")
        )
    if os.getenv("UVICORN_TIMEOUT_NOTIFY"):
        config_kwargs["timeout_notify"] = int(os.getenv("UVICORN_TIMEOUT_NOTIFY"))
    if os.getenv("UVICORN_SSL_KEYFILE"):
        config_kwargs["ssl_keyfile"] = os.getenv("UVICORN_SSL_KEYFILE")
    if os.getenv("UVICORN_SSL_CERTFILE"):
        config_kwargs["ssl_certfile"] = os.getenv("UVICORN_SSL_CERTFILE")
    if os.getenv("UVICORN_SSL_KEYFILE_PASSWORD"):
        config_kwargs["ssl_keyfile_password"] = os.getenv(
            "UVICORN_SSL_KEYFILE_PASSWORD"
        )
    if os.getenv("UVICORN_SSL_VERSION"):
        config_kwargs["ssl_version"] = int(os.getenv("UVICORN_SSL_VERSION"))
    if os.getenv("UVICORN_SSL_CERT_REQS"):
        config_kwargs["ssl_cert_reqs"] = int(os.getenv("UVICORN_SSL_CERT_REQS"))
    if os.getenv("UVICORN_SSL_CA_CERTS"):
        config_kwargs["ssl_ca_certs"] = os.getenv("UVICORN_SSL_CA_CERTS")
    if os.getenv("UVICORN_SSL_CIPHERS"):
        config_kwargs["ssl_ciphers"] = os.getenv("UVICORN_SSL_CIPHERS")
    if os.getenv("UVICORN_HEADERS"):
        config_kwargs["headers"] = [
            tuple(h.split(":", 1))
            for h in os.getenv("UVICORN_HEADERS").split(",")
            if ":" in h
        ]
    if os.getenv("UVICORN_USE_COLORS"):
        config_kwargs["use_colors"] = os.getenv("UVICORN_USE_COLORS").lower() == "true"
    if os.getenv("UVICORN_UDS"):
        config_kwargs["uds"] = os.getenv("UVICORN_UDS")
    if os.getenv("UVICORN_FD"):
        config_kwargs["fd"] = int(os.getenv("UVICORN_FD"))
    if os.getenv("UVICORN_ROOT_PATH"):
        config_kwargs["root_path"] = os.getenv("UVICORN_ROOT_PATH")

    config = uvicorn.Config(**config_kwargs)
    uvicorn.run(config)
