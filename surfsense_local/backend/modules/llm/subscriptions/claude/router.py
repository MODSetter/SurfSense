from fastapi import APIRouter, HTTPException, status

from api.dependencies import SessionDep
from modules.llm.connections.router import connection_read
from modules.llm.connections.serves import served_by
from modules.llm.schemas import ConnectionRead
from modules.llm.subscriptions.claude import account
from modules.llm.subscriptions.claude.hosts import hosts_still_off, require_claude_hosts
from modules.llm.subscriptions.claude.locate import this_machines_claude
from modules.llm.subscriptions.claude.proxy import claude_proxy_url
from modules.llm.subscriptions.claude.schemas import (
    ClaudeConnectionWrite,
    ClaudeHost,
    ClaudeOption,
    ClaudeStatusRead,
)
from modules.llm.subscriptions.claude.status import ClaudeState, read_status

router = APIRouter(prefix="/connections")


@router.get("/claude")
def claude_option(session: SessionDep) -> ClaudeOption:
    """What a picker needs to offer the plan, at once: it runs no Claude Code."""
    hosts = [
        ClaudeHost(destination=f"host:{host}", host=host)
        for host in hosts_still_off(session)
    ]
    return ClaudeOption(serves=list(served_by(account.CLAUDE_PLAN)), hosts=hosts)


@router.get("/claude/status")
def claude_status() -> ClaudeStatusRead:
    """Claude Code's state on this machine, read live, so signing in or out in a
    terminal shows on the next look."""
    found = read_status(this_machines_claude(), proxy_url=claude_proxy_url())
    return ClaudeStatusRead(
        state=found.state, version=found.version, email=found.email, plan=found.plan
    )


@router.post("/claude", status_code=status.HTTP_201_CREATED)
def connect_claude(
    payload: ClaudeConnectionWrite, session: SessionDep
) -> ConnectionRead:
    """A Claude plan connection, once Claude Code is signed in and Anthropic allowed."""
    label = payload.label.strip()
    if not label:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "label must not be empty"
        )
    require_claude_hosts(session)
    found = read_status(this_machines_claude(), proxy_url=claude_proxy_url())
    if found.state is not ClaudeState.READY:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            {"state": found.state.value, "message": "Claude Code is not ready"},
        )
    try:
        connection = account.add_claude_plan(session, label)
    except account.ClaudePlanExistsError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    session.commit()
    return connection_read(connection)
