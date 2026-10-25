"""The caller's IP address behind Cloudflare and the Coolify proxy, for the rate limits."""

from starlette.requests import Request


def get_real_client_ip(request: Request) -> str:
    """CF-Connecting-IP, then X-Real-IP, then X-Forwarded-For's first entry, then the socket peer."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
