"""Workspace git-remote HTTP adapter."""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.context import AuthContext
from app.config import config
from app.db import Permission, get_async_session
from app.knowledge_store import KnowledgeStore
from app.knowledge_store.remote.api.schemas import (
    GithubInstallRead,
    GithubRepoRead,
    RemoteAddRequest,
    RemoteStatusRead,
    ResolveRequest,
)
from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges.github import GithubProvider
from app.knowledge_store.remote.queue import enqueue_sync
from app.knowledge_store.remote.schemas import GithubSpec, GitlabSpec
from app.users import get_auth_context
from app.utils.oauth_security import OAuthStateManager
from app.utils.rbac import check_permission, check_workspace_access

router = APIRouter(tags=["git-remotes"])

_STATUS = {
    "not_git_native": 409,
    "already_exists": 409,
    "not_empty": 409,
    "invalid_spec": 400,
    "missing": 404,
    "forge": 503,
    "need_direction": 409,
    "unsafe_path": 400,
}


def _http(error: RemoteError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(error.code, 400), detail=error.message)


@router.get(
    "/workspaces/{workspace_id}/git-remotes",
    response_model=list[RemoteStatusRead],
)
async def list_git_remotes(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[RemoteStatusRead]:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_VIEW.value)
    store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
    remotes = await store.remotes.list()
    return [RemoteStatusRead.model_validate(r, from_attributes=True) for r in remotes]


@router.post(
    "/workspaces/{workspace_id}/git-remotes",
    response_model=RemoteStatusRead,
)
async def add_git_remote(
    workspace_id: int,
    body: RemoteAddRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> RemoteStatusRead:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
    spec = (
        GithubSpec(
            provider="github",
            url=str(body.url),
            installation_id=body.installation_id,
            branch=body.branch,
            sourcepath=body.sourcepath,
        )
        if body.provider == "github"
        else GitlabSpec(
            provider="gitlab",
            url=str(body.url),
            token=body.token,
            branch=body.branch,
            sourcepath=body.sourcepath,
        )
    )
    try:
        status = await store.remotes.add(spec, direction=body.direction)
    except RemoteError as exc:
        raise _http(exc) from exc
    return RemoteStatusRead.model_validate(status, from_attributes=True)


@router.delete("/workspaces/{workspace_id}/git-remotes", status_code=204)
async def remove_git_remote(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> None:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
    await store.remotes.remove()


@router.post("/workspaces/{workspace_id}/git-remotes/sync", status_code=202)
async def retry_git_remote_sync(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, str]:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    enqueue_sync(workspace_id)
    return {"status": "queued"}


@router.post("/workspaces/{workspace_id}/git-remotes/resolve", status_code=202)
async def resolve_git_remote(
    workspace_id: int,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> dict[str, str]:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    store = KnowledgeStore.for_workspace(workspace_id).with_session(session)
    try:
        await store.remotes.resolve(direction=body.direction)
    except RemoteError as exc:
        raise _http(exc) from exc
    enqueue_sync(workspace_id)
    return {"status": "queued"}


@router.get(
    "/workspaces/{workspace_id}/git-remotes/github/install",
    response_model=GithubInstallRead,
)
async def github_install_url(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> GithubInstallRead:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    if not auth.user:
        raise HTTPException(status_code=401, detail="session required")
    state = OAuthStateManager(config.SECRET_KEY).generate_secure_state(
        workspace_id, auth.user.id
    )
    try:
        url = GithubProvider().install_url(state=state)
    except RemoteError as exc:
        raise _http(exc) from exc
    return GithubInstallRead(url=url)


@router.get("/workspaces/git-remotes/github/callback")
async def github_install_callback(
    installation_id: str = Query(...),
    state: str = Query(...),
    setup_action: str | None = Query(None),
) -> RedirectResponse:
    data = OAuthStateManager(config.SECRET_KEY).validate_state(state)
    workspace_id = int(data["space_id"])
    qs = urlencode({"github_installation_id": installation_id})
    return RedirectResponse(
        url=f"{config.NEXT_FRONTEND_URL}/dashboard/{workspace_id}/workspace-settings/git-remote?{qs}"
    )


@router.get(
    "/workspaces/{workspace_id}/git-remotes/github/authorize",
    response_model=GithubInstallRead,
)
async def github_authorize_url(
    workspace_id: int,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> GithubInstallRead:
    """Start user-to-server OAuth so the callback can list this user's installs."""
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    if not auth.user:
        raise HTTPException(status_code=401, detail="session required")
    state = OAuthStateManager(config.SECRET_KEY).generate_secure_state(
        workspace_id, auth.user.id
    )
    try:
        url = GithubProvider().oauth_authorize_url(state=state)
    except RemoteError as exc:
        raise _http(exc) from exc
    return GithubInstallRead(url=url)


def _github_callback_target(workspace_id: int, installations: list[dict]) -> str:
    """Frontend URL after OAuth: pick the sole install, or offer a choice."""
    base = (
        f"{config.NEXT_FRONTEND_URL}/dashboard/{workspace_id}"
        "/workspace-settings/git-remote"
    )
    if not installations:
        return f"{base}?{urlencode({'github_error': 'no_installation'})}"
    if len(installations) == 1:
        return f"{base}?{urlencode({'github_installation_id': installations[0]['id']})}"
    encoded = ",".join(f"{i['id']}:{i['account']}" for i in installations)
    return f"{base}?{urlencode({'github_installations': encoded})}"


@router.get("/workspaces/git-remotes/github/oauth/callback")
async def github_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    data = OAuthStateManager(config.SECRET_KEY).validate_state(state)
    workspace_id = int(data["space_id"])
    base = (
        f"{config.NEXT_FRONTEND_URL}/dashboard/{workspace_id}"
        "/workspace-settings/git-remote"
    )
    provider = GithubProvider()
    try:
        token = await provider.exchange_user_code(code)
        installations = await provider.list_user_installations(token)
    except RemoteError:
        return RedirectResponse(
            url=f"{base}?{urlencode({'github_error': 'oauth_failed'})}"
        )
    return RedirectResponse(url=_github_callback_target(workspace_id, installations))


@router.get("/workspaces/{workspace_id}/git-remotes/github/folders")
async def github_list_folders(
    workspace_id: int,
    installation_id: str,
    full_name: str,
    branch: str = "main",
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[str]:
    """Folders under ``branch`` of the repo, so sourcepath is a real choice."""
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    try:
        return await GithubProvider().list_tree_folders(
            installation_id=installation_id, full_name=full_name, branch=branch
        )
    except RemoteError as exc:
        raise _http(exc) from exc


@router.get(
    "/workspaces/{workspace_id}/git-remotes/github/repos",
    response_model=list[GithubRepoRead],
)
async def github_list_repos(
    workspace_id: int,
    installation_id: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[GithubRepoRead]:
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    try:
        repos = await GithubProvider().list_repos(installation_id)
    except RemoteError as exc:
        raise _http(exc) from exc
    return [
        GithubRepoRead(
            full_name=r["full_name"],
            url=r["url"],
            default_branch=r.get("default_branch") or "main",
        )
        for r in repos
    ]


@router.get("/workspaces/{workspace_id}/git-remotes/github/branches")
async def github_list_branches(
    workspace_id: int,
    installation_id: str,
    full_name: str,
    session: AsyncSession = Depends(get_async_session),
    auth: AuthContext = Depends(get_auth_context),
) -> list[str]:
    """Branch names on the repo, so branch is a picker not a guess."""
    await check_workspace_access(session, auth, workspace_id)
    await check_permission(session, auth, workspace_id, Permission.SETTINGS_UPDATE.value)
    try:
        return await GithubProvider().list_branches(
            installation_id=installation_id, full_name=full_name
        )
    except RemoteError as exc:
        raise _http(exc) from exc
