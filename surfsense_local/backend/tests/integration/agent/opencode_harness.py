"""Starting the staged opencode the way Electron does, against a scripted model.

Skips where `pnpm build:opencode` has not staged a build, as the parser tests
skip without their pack: CI's backend jobs do not stage desktop runtimes.
"""

import json
import os
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import httpx
import pytest

STAGED = (
    Path(__file__).resolve().parents[4]
    / "electron"
    / "opencode"
    / ("opencode.exe" if os.name == "nt" else "opencode")
)
MODEL = "stub-model"

# What Electron's launch passes on from the system (sidecars/opencode.ts); on
# Windows the Bun binary dies at start (0xC0000409) without SYSTEMROOT.
FROM_THE_SYSTEM = (
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
)


def needs_staged_opencode() -> None:
    """Skip unless the pinned opencode is staged in electron/opencode/."""
    if not STAGED.is_file():
        pytest.skip(
            "run `pnpm build:opencode` in surfsense_local/electron to exercise opencode"
        )


@dataclass
class ScriptedModel:
    """An OpenAI-compatible model that plays its replies in order, one per request.

    A reply is ("text", words), ("bash", command) for one shell call,
    ("call", JSON of {"name", "arguments"}) for any other tool call, ("calls",
    a JSON list of them) for several in one step, ("say-and-call", JSON of
    {"say", "call"}) for words and then a call in one step, as Claude often
    answers, ("call-filling-the-window",
    JSON as for "call"), whose usage says the context is full so opencode
    compacts before the next step, ("stall", words), which sends its words
    and then waits until released, or ("too-long", ""), which refuses the
    request as llama-server does one larger than its context.
    """

    url: str = ""
    replies: list[tuple[str, str]] = field(default_factory=list)
    requests: list[dict] = field(default_factory=list)
    release: threading.Event = field(default_factory=threading.Event)


# More tokens than any window SurfSense configures, so opencode's overflow check trips.
_FULL_WINDOW_TOKENS = 2_000_000


def _chunk(delta: dict, finish: str | None = None, usage: dict | None = None) -> str:
    """One streamed chat completion chunk, as an OpenAI-compatible server sends it."""
    choice = {"index": 0, "delta": delta, "finish_reason": finish}
    chunk = {"id": "c1", "object": "chat.completion.chunk", "choices": [choice]}
    if usage is not None:
        chunk["usage"] = usage
    return "data: " + json.dumps(chunk) + "\n\n"


class ScriptedHandler(BaseHTTPRequestHandler):
    """Streams the next scripted reply for every chat request."""

    def do_POST(self) -> None:
        model: ScriptedModel = self.server.model  # type: ignore[attr-defined]
        model.requests.append(
            json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        )
        kind, value = model.replies.pop(0) if model.replies else ("text", "Done.")
        if kind == "too-long":
            self._refuse_as_too_long()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        if kind in ("bash", "call", "calls", "say-and-call", "call-filling-the-window"):
            wanted = (
                [
                    {
                        "name": "bash",
                        "arguments": {"command": value, "description": "Run it"},
                    }
                ]
                if kind == "bash"
                else json.loads(value)
            )
            if kind == "say-and-call":
                self._send(_chunk({"role": "assistant", "content": wanted["say"]}))
                wanted = wanted["call"]
            calls = [
                {
                    "index": index,
                    "id": f"call_{index + 1}",
                    "type": "function",
                    "function": {
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"]),
                    },
                }
                for index, call in enumerate(
                    wanted if isinstance(wanted, list) else [wanted]
                )
            ]
            usage = (
                {
                    "prompt_tokens": _FULL_WINDOW_TOKENS,
                    "completion_tokens": 10,
                    "total_tokens": _FULL_WINDOW_TOKENS + 10,
                }
                if kind == "call-filling-the-window"
                else None
            )
            self._send(
                _chunk({"role": "assistant", "tool_calls": calls}),
                _chunk({}, "tool_calls", usage),
            )
        else:
            self._send(_chunk({"role": "assistant", "content": value}))
            if kind == "stall":
                model.release.wait(timeout=30)
            self._send(_chunk({}, "stop"))
        self._send("data: [DONE]\n\n")

    def _refuse_as_too_long(self) -> None:
        """llama-server's answer to a request larger than its context (b11050)."""
        body = json.dumps(
            {
                "error": {
                    "code": 400,
                    "message": "request (40960 tokens) exceeds the available "
                    "context size (32768 tokens), try increasing it",
                    "type": "exceed_context_size_error",
                }
            }
        ).encode()
        self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send(self, *frames: str) -> None:
        """Write and flush, as a model streaming token by token does."""
        try:
            for frame in frames:
                self.wfile.write(frame.encode())
                self.wfile.flush()
        except OSError:
            pass  # opencode hung up, which a stopped turn does

    def log_message(self, *args: object) -> None:
        """Keep the request log out of the test output."""


def free_port() -> int:
    """A loopback port nothing listens on yet."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@dataclass
class RunningOpencode:
    """A started opencode: where it listens, its password, and the folders it uses."""

    url: str
    password: str
    agent_dir: Path
    process: subprocess.Popen

    def stop(self) -> None:
        """Take down opencode and anything it started, as the supervisor does."""
        if self.process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/pid", str(self.process.pid), "/t", "/f"], check=False
            )
        else:
            os.killpg(self.process.pid, signal.SIGKILL)
        self.process.wait(timeout=10)


def start_opencode(agent_dir: Path, port: int, password: str) -> RunningOpencode:
    """Start the staged opencode on the configuration in `agent_dir`, as Electron would."""
    home = agent_dir / "opencode"
    config_folder = home / "config" / "opencode"
    (config_folder / "node_modules").mkdir(parents=True, exist_ok=True)
    lock = {
        "lockfileVersion": 3,
        "packages": {"": {"dependencies": {"@opencode-ai/plugin": "*"}}},
    }
    (config_folder / "package-lock.json").write_text(json.dumps(lock))
    nowhere = "http://127.0.0.1:9"
    env = {
        **{name: os.environ[name] for name in FROM_THE_SYSTEM if name in os.environ},
        "PATH": f"{STAGED.parent}{os.pathsep}{os.environ.get('PATH', '')}",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "OPENCODE_TEST_HOME": str(home),
        "XDG_CONFIG_HOME": str(home / "config"),
        "XDG_DATA_HOME": str(home / "data"),
        "XDG_CACHE_HOME": str(home / "cache"),
        "XDG_STATE_HOME": str(home / "state"),
        "OPENCODE_CONFIG": str(agent_dir / "opencode.json"),
        "OPENCODE_SERVER_PASSWORD": password,
        "npm_config_audit": "false",
        "npm_config_fetch_retries": "0",
        "HTTP_PROXY": nowhere,
        "HTTPS_PROXY": nowhere,
        "ALL_PROXY": nowhere,
        "NO_PROXY": "127.0.0.1,localhost,::1",
        **dict.fromkeys(
            (
                "OPENCODE_DISABLE_MODELS_FETCH",
                "OPENCODE_DISABLE_SHARE",
                "OPENCODE_DISABLE_LSP_DOWNLOAD",
                "OPENCODE_DISABLE_AUTOUPDATE",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS",
                "OPENCODE_PURE",
                "OPENCODE_DISABLE_PROJECT_CONFIG",
                "OPENCODE_DISABLE_EXTERNAL_SKILLS",
                "OPENCODE_DISABLE_CLAUDE_CODE",
            ),
            "1",
        ),
    }
    for folder in ("data", "cache", "state"):
        (home / folder).mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [str(STAGED), "serve", "--hostname", "127.0.0.1", "--port", str(port)],
        cwd=home,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return RunningOpencode(f"http://127.0.0.1:{port}", password, agent_dir, process)


def wait_until_healthy(running: RunningOpencode, timeout: float = 60.0) -> None:
    """Block until opencode answers its health route, or fail the test.

    The port opens before the server answers on it, so only an answer counts.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if running.process.poll() is not None:
            raise RuntimeError(f"opencode exited with {running.process.returncode}")
        try:
            reply = httpx.get(
                f"{running.url}/global/health",
                auth=("opencode", running.password),
                timeout=1.0,
            )
            if reply.status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError("opencode never answered its health route")


class StandInForElectron:
    """Electron's agent watcher: starts opencode once its config file exists, and never on a rewrite.

    A rewrite is the API's to apply, through opencode's own reload.
    """

    def __init__(self, agent_dir: Path, port: int, password: str) -> None:
        self._config = agent_dir / "opencode.json"
        self._agent_dir, self._port, self._password = agent_dir, port, password
        self._stopping = threading.Event()
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self.running: RunningOpencode | None = None
        self.starts = 0

    def __enter__(self) -> "StandInForElectron":
        self._follow()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stopping.set()
        self._thread.join(timeout=10)
        if self.running is not None:
            self.running.stop()

    def _watch(self) -> None:
        """Check for the file, as the real watcher polls for it."""
        while not self._stopping.wait(0.2):
            self._follow()

    def _follow(self) -> None:
        """Start opencode the first time the file is there."""
        if self.running is None and self._config.is_file():
            self.running = start_opencode(self._agent_dir, self._port, self._password)
            self.starts += 1
