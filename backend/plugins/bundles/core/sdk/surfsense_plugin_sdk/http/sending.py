"""Sends a plugin's request, logging whom it reached and never what it asked."""

import json as json_codec
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from surfsense_plugin_sdk.http.declared_hosts import checked_host
from surfsense_plugin_sdk.http.headers import Headers
from surfsense_plugin_sdk.http.redirects import CheckEveryHop
from surfsense_plugin_sdk.http.response import Response
from surfsense_plugin_sdk.run.current_run import current_run

# Per request, so a silent source fails the call rather than the whole run.
TIMEOUT_SECONDS = 30

type Params = Mapping[str, str | int | float]

_opener_checking_redirects = urllib.request.build_opener(CheckEveryHop)


def request(
    method: str,
    url: str,
    *,
    params: Params | None = None,
    headers: Mapping[str, str] | None = None,
    json: object = None,
    data: bytes | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> Response:
    """Sends any method to a declared host; any status comes back, no answer raises."""
    if json is not None and data is not None:
        raise ValueError("pass json= or data=, not both")
    if params:
        separator = "&" if urllib.parse.urlsplit(url).query else "?"
        url = f"{url}{separator}{urllib.parse.urlencode(params)}"
    host = checked_host(url)

    sent = dict(headers or {})
    # Sources often refuse Python's own agent.
    _add_header_unless_set(
        sent, "User-Agent", f"SurfSense-Plugin/{current_run().manifest['id']}"
    )
    if json is not None:
        data = json_codec.dumps(json).encode()
        _add_header_unless_set(sent, "Content-Type", "application/json")

    outgoing = urllib.request.Request(url, data=data, headers=sent, method=method)
    try:
        with _opener_checking_redirects.open(outgoing, timeout=timeout) as reply:
            response = Response(
                reply.status, Headers(reply.headers.items()), reply.read()
            )
            final_url: str = reply.url
    except urllib.error.HTTPError as answer:
        response = Response(answer.code, Headers(answer.headers.items()), answer.read())
        final_url = answer.url
    except OSError as failure:
        reason = _why(failure)
        _log(method, host, f"failed: {reason}")
        raise ConnectionError(f"could not reach {host}: {reason}") from None

    _log(method, urllib.parse.urlsplit(final_url).hostname, response.status)
    return response


def get(
    url: str,
    *,
    params: Params | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> Response:
    """Fetches from a declared host; any status comes back, no answer raises."""
    return request("GET", url, params=params, headers=headers, timeout=timeout)


def post(
    url: str,
    *,
    params: Params | None = None,
    headers: Mapping[str, str] | None = None,
    json: object = None,
    data: bytes | None = None,
    timeout: float = TIMEOUT_SECONDS,
) -> Response:
    """Posts JSON with json= or raw bytes with data= to a declared host."""
    return request(
        "POST",
        url,
        params=params,
        headers=headers,
        json=json,
        data=data,
        timeout=timeout,
    )


def _add_header_unless_set(headers: dict[str, str], name: str, value: str) -> None:
    """Adds a header the author did not set, however they wrote its name."""
    if not any(given.lower() == name.lower() for given in headers):
        headers[name] = value


def _why(failure: OSError) -> str:
    """The system's own words for a failed connection, without urllib's wrapping."""
    cause = failure.reason if isinstance(failure, urllib.error.URLError) else failure
    if isinstance(cause, OSError) and cause.strerror:
        return cause.strerror
    return str(cause)


def _log(method: str, host: str | None, outcome: object) -> None:
    """One line of the run's log: whom the plugin reached, never what it asked."""
    sys.stderr.write(f"http: {method} {host} {outcome}\n")
