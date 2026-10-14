"""The one way to the transcription server: one request at a time, a speaker's
phrase ahead of a recording's window, and no window while someone dictates or
a podcast or an image holds the text runtime."""

import asyncio

import pytest

from modules.llm.transcription.gate import TranscriptionGate, WindowWaitError

pytestmark = [pytest.mark.unit, pytest.mark.asyncio]

MODEL = "nemotron"


class Server:
    """What reached the server, in order."""

    def __init__(self) -> None:
        self.log: list[str] = []

    async def unload(self, model: str) -> None:
        self.log.append(f"unload {model}")


def gate_for(server: Server, dictating: list[bool] | None = None) -> TranscriptionGate:
    """A gate over the stub, with a dictation open or not."""
    flag = dictating if dictating is not None else [False]
    return TranscriptionGate(
        dictating=lambda: flag[0], unload=server.unload, poll_seconds=0.01
    )


async def request(
    gate: TranscriptionGate, server: Server, name: str, release: asyncio.Event
) -> None:
    """Take a turn, as a phrase or a window by its name, until released."""
    turn = (
        gate.window_turn(MODEL, wait_seconds=5)
        if "window" in name
        else (gate.dictation_turn(MODEL))
    )
    async with turn:
        server.log.append(f"start {name}")
        await release.wait()
        server.log.append(f"end {name}")


async def settle() -> None:
    """Let every waiting task run as far as it can."""
    for _ in range(20):
        await asyncio.sleep(0)


async def test_one_request_at_a_time() -> None:
    """The server runs one model and one request at a time anyway."""
    server = Server()
    gate = gate_for(server)
    first, second = asyncio.Event(), asyncio.Event()

    running = [
        asyncio.create_task(request(gate, server, "phrase 1", first)),
        asyncio.create_task(request(gate, server, "phrase 2", second)),
    ]
    await settle()
    started_together = server.log.count("start phrase 1") + server.log.count(
        "start phrase 2"
    )
    first.set()
    second.set()
    await asyncio.gather(*running)

    assert started_together == 1
    assert server.log[1].startswith("end")


async def test_a_phrase_goes_ahead_of_a_window_that_waited_longer() -> None:
    """A phrase waits at most for the window in flight."""
    server = Server()
    gate = gate_for(server)
    in_flight, next_window, phrase = asyncio.Event(), asyncio.Event(), asyncio.Event()

    first = asyncio.create_task(request(gate, server, "window 1", in_flight))
    await settle()
    waiting_window = asyncio.create_task(request(gate, server, "window 2", next_window))
    await settle()
    waiting_phrase = asyncio.create_task(request(gate, server, "phrase", phrase))
    await settle()
    for event in (in_flight, phrase, next_window):
        event.set()
    await asyncio.gather(first, waiting_window, waiting_phrase)

    assert [entry for entry in server.log if entry.startswith("start")] == [
        "start window 1",
        "start phrase",
        "start window 2",
    ]


async def test_an_open_dictation_keeps_windows_off_the_server() -> None:
    """From the mic press until the last phrase."""
    server = Server()
    gate = gate_for(server, dictating=[True])

    with pytest.raises(WindowWaitError) as waited:
        async with gate.window_turn(MODEL, wait_seconds=0.05):
            server.log.append("window")

    assert waited.value.reason == "dictation"
    assert server.log == []


async def test_a_window_starts_once_the_dictation_ends() -> None:
    """Its quiet end is a time, so waiting windows look again."""
    dictating = [True]
    server = Server()
    gate = gate_for(server, dictating)

    async def window() -> None:
        async with gate.window_turn(MODEL, wait_seconds=5):
            server.log.append("window")

    waiting = asyncio.create_task(window())
    await asyncio.sleep(0.05)
    started_while_dictating = list(server.log)
    dictating[0] = False
    await asyncio.wait_for(waiting, 1)

    assert (started_while_dictating, server.log) == ([], ["window"])


async def test_a_hold_waits_for_the_window_in_flight_then_unloads_the_model() -> None:
    """A podcast or an image takes the memory; the window being transcribed
    finishes first, and no other starts until the hold ends."""
    server = Server()
    gate = gate_for(server)
    in_flight = asyncio.Event()
    window = asyncio.create_task(request(gate, server, "window", in_flight))
    await settle()
    granted = asyncio.Event()
    release = asyncio.Event()

    async def hold() -> None:
        async with gate.text_runtime_held():
            server.log.append("held")
            granted.set()
            await release.wait()

    holding = asyncio.create_task(hold())
    await settle()
    granted_before_window_ended = granted.is_set()
    in_flight.set()
    await asyncio.wait_for(granted.wait(), 1)

    with pytest.raises(WindowWaitError) as waited:
        async with gate.window_turn(MODEL, wait_seconds=0.05):
            server.log.append("window during the hold")
    release.set()
    await asyncio.gather(window, holding)

    assert not granted_before_window_ended
    assert waited.value.reason == "hold"
    assert server.log == ["start window", "end window", f"unload {MODEL}", "held"]


async def test_dictation_stays_available_during_a_hold() -> None:
    """A podcast's voicing then shares the CPU with the phrases."""
    server = Server()
    gate = gate_for(server)
    release = asyncio.Event()

    async def hold() -> None:
        async with gate.text_runtime_held():
            await release.wait()

    holding = asyncio.create_task(hold())
    await settle()
    async with gate.dictation_turn(MODEL):
        server.log.append("phrase")
    release.set()
    await holding

    assert server.log == ["phrase"]


async def test_windows_go_again_once_the_hold_ends() -> None:
    """The hold leaves nothing behind."""
    server = Server()
    gate = gate_for(server)

    async with gate.text_runtime_held():
        pass
    async with gate.window_turn(MODEL, wait_seconds=0.05):
        server.log.append("window")

    assert server.log == ["window"]


async def test_a_hold_whose_caller_leaves_lets_windows_go() -> None:
    """The worker holding it died or closed the request mid-wait."""
    server = Server()
    gate = gate_for(server)
    in_flight = asyncio.Event()
    window = asyncio.create_task(request(gate, server, "window", in_flight))
    await settle()

    async def hold() -> None:
        async with gate.text_runtime_held():
            await asyncio.Event().wait()

    holding = asyncio.create_task(hold())
    await settle()
    holding.cancel()
    await asyncio.gather(holding, return_exceptions=True)
    in_flight.set()
    await window
    async with gate.window_turn(MODEL, wait_seconds=0.05):
        server.log.append("window after")

    assert server.log[-1] == "window after"
