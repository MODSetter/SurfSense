import socket

import pytest

pytestmark = pytest.mark.unit


def _declaring_localhost(plugin) -> None:
    """Lets the plugin reach the source stub under the name localhost."""
    plugin.manifest["hosts"] = ["localhost"]


def test_a_declared_host_is_reached_and_logged_without_its_path(plugin, source) -> None:
    """The log says who the plugin talked to, never what it asked for."""
    _declaring_localhost(plugin)
    source.answer("GET", "/search?query=plugins&page=2", 200, {"hits": ["one", "two"]})
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    response = http.get(
        "http://localhost:{source.port}/search",
        params={{"query": "plugins", "page": 2}},
        headers={{"Authorization": "Bearer t0ken"}},
    )
    print(response.status, response.headers["content-type"], response.json()["hits"])
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "200 application/json ['one', 'two']\n"
    [request] = source.received
    assert request.headers["Authorization"] == "Bearer t0ken"
    assert finished.stderr == "http: GET localhost 200\n"


def test_a_status_code_is_returned_not_raised(plugin, source) -> None:
    """A 404 is an answer the plugin decides about; only no answer at all raises."""
    _declaring_localhost(plugin)
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    response = http.get("http://localhost:{source.port}/gone")
    print(response.status, response.text)
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == '404 {"detail": "Not Found"}\n'


def test_post_sends_its_json_body(plugin, source) -> None:
    """The body a source's API expects arrives as JSON."""
    _declaring_localhost(plugin)
    source.answer("POST", "/graphql", 200, {"data": None})
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.post("http://localhost:{source.port}/graphql", json={{"query": text}})
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    [request] = source.received
    assert request.body == {"query": "hi"}
    assert request.headers["Content-Type"] == "application/json"


def test_an_undeclared_host_is_refused_before_any_connection(plugin, source) -> None:
    """127.0.0.1 is the same server as localhost, but it is not the declared name."""
    _declaring_localhost(plugin)
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get("http://127.0.0.1:{source.port}/search")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "HostNotDeclared" in finished.stderr
    assert '"127.0.0.1"' in finished.stderr
    assert source.received == []


def test_a_redirect_to_an_undeclared_host_is_refused(plugin, source) -> None:
    """Every hop is checked, so a declared host cannot hand the plugin elsewhere."""
    _declaring_localhost(plugin)
    source.answer(
        "GET",
        "/start",
        302,
        None,
        headers={"Location": f"http://127.0.0.1:{source.port}/elsewhere"},
    )
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get("http://localhost:{source.port}/start")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "HostNotDeclared" in finished.stderr
    assert [r.path for r in source.received] == ["/start"]


def test_only_web_addresses_are_fetched(plugin) -> None:
    """A file: URL is not a request to a host, so http refuses it by what it is."""
    plugin.write(
        """
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get("file:///etc/hostname")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "http and https only" in finished.stderr


def test_a_header_is_found_however_it_is_written(plugin, source) -> None:
    """Header names are case-insensitive in HTTP, so they are here too."""
    _declaring_localhost(plugin)
    source.answer("GET", "/", 200, {})
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    headers = http.get("http://localhost:{source.port}/").headers
    print(headers["Content-Type"], headers["content-type"], "X-Absent" in headers)
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    assert finished.stdout == "application/json application/json False\n"


@pytest.mark.parametrize(
    ("headers", "user_agent"),
    [
        ("{}", "SurfSense-Plugin/example"),
        ('{"User-Agent": "hn-bot/1.0"}', "hn-bot/1.0"),
    ],
)
def test_a_request_names_the_plugin_unless_the_author_says_otherwise(
    plugin, source, headers: str, user_agent: str
) -> None:
    """Sources refuse Python's default agent, and may ask who is calling."""
    _declaring_localhost(plugin)
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get("http://localhost:{source.port}/", headers={headers})
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    [request] = source.received
    assert request.headers["User-Agent"] == user_agent


FOLLOWS_A_REDIRECT_WITH_CREDENTIALS = """
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get(
        "http://localhost:{port}/start",
        headers={{"Authorization": "Bearer t0ken", "Cookie": "session=1"}},
    )
"""


def test_credentials_do_not_follow_a_redirect_to_another_host(plugin, source) -> None:
    """A token meant for one host is not handed to the next, declared or not."""
    plugin.manifest["hosts"] = ["localhost", "127.0.0.1"]
    source.answer(
        "GET", "/start", 302, None, headers={"Location": f"{source.url}/next"}
    )
    source.answer("GET", "/next", 200, {})
    plugin.write(FOLLOWS_A_REDIRECT_WITH_CREDENTIALS.format(port=source.port))

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    first, second = source.received
    assert first.headers["Authorization"] == "Bearer t0ken"
    assert "Authorization" not in second.headers
    assert "Cookie" not in second.headers


def test_credentials_follow_a_redirect_on_the_same_host(plugin, source) -> None:
    """Moving within one host is the same source, so the token still applies."""
    _declaring_localhost(plugin)
    source.answer(
        "GET",
        "/start",
        302,
        None,
        headers={"Location": f"http://localhost:{source.port}/next"},
    )
    source.answer("GET", "/next", 200, {})
    plugin.write(FOLLOWS_A_REDIRECT_WITH_CREDENTIALS.format(port=source.port))

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 0, finished.stderr
    _, second = source.received
    assert second.headers["Authorization"] == "Bearer t0ken"


def test_a_source_that_does_not_answer_is_named_in_the_log(plugin) -> None:
    """The user reads which source failed, not urllib's internals."""
    _declaring_localhost(plugin)
    with socket.socket() as unused:
        unused.bind(("127.0.0.1", 0))
        closed_port = unused.getsockname()[1]
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.get("http://localhost:{closed_port}/")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "http: GET localhost failed: Connection refused\n" in finished.stderr
    assert "ConnectionError: could not reach localhost: Connection refused" in (
        finished.stderr
    )
    assert "urlopen error" not in finished.stderr


def test_a_body_is_json_or_bytes_never_both(plugin, source) -> None:
    """Refused before sending, so neither body is dropped without the author knowing."""
    _declaring_localhost(plugin)
    plugin.write(
        f"""
from surfsense_plugin_sdk import action, http


@action("echo")
def echo(text: str) -> None:
    http.post("http://localhost:{source.port}/", json={{"q": text}}, data=b"q=hi")
"""
    )

    finished = plugin.run("echo", {"text": "hi"})

    assert finished.returncode == 1
    assert "ValueError: pass json= or data=, not both" in finished.stderr
    assert source.received == []
