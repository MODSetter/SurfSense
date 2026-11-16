"""The registry as Settings > Plugins lists it: each entry, whether it is verified, and whether it is connected."""

from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.registry.current_registry import CurrentRegistry
from modules.plugins.lists.registry.registry_icons import icon_file

VERIFIED = "verified"


class EntryHeaderRead(BaseModel):
    name: str
    label: str | None
    description: str | None


class RegistryEntryRead(BaseModel):
    id: str
    name: str
    description: str
    author: str
    # `verified` (a maintainer judged that its author runs the server) or `community`.
    verification: str
    verified: bool
    access: str
    access_note: str | None
    # `none`, `token` or `oauth`; a token entry says what key to paste.
    auth_type: str
    auth_title: str | None
    auth_description: str | None
    # A `headers` entry's headers, each to be given a value; never a value itself.
    auth_headers: list[EntryHeaderRead] = []
    # An `oauth` entry whose provider takes only apps registered in advance.
    user_client: bool = False
    hosts: list[str]
    # The host every call goes to; the rest, an OAuth plugin's, see only the sign-in.
    server_host: str
    sign_in_hosts: list[str]
    homepage: str | None
    privacy_policy: str | None
    # What its page shows before it is connected; `tools` is None when the entry lists none.
    about: str | None
    tools: list[str] | None
    # `YYYY-MM`, the month it joined the registry; None in an older entry.
    added: str | None
    has_icon: bool
    connected: bool


class RemovedEntryRead(BaseModel):
    id: str
    reason: str


class RegistryRead(BaseModel):
    # True while third-party plugins are off: then nothing is fetched or listed.
    third_party_off: bool
    # When this copy was fetched; the list is shown from it while offline.
    fetched_at: datetime | None = None
    plugins: list[RegistryEntryRead] = []
    removed: list[RemovedEntryRead] = []


def read_registry(session: Session, current: CurrentRegistry) -> RegistryRead:
    return RegistryRead(
        third_party_off=False,
        fetched_at=current.fetched_at,
        plugins=[
            RegistryEntryRead(
                id=entry.id,
                name=entry.name,
                description=entry.description,
                author=entry.author,
                verification=entry.verification,
                verified=entry.verification == VERIFIED,
                access=entry.access,
                access_note=entry.access_note,
                auth_type=entry.auth.type,
                auth_title=entry.auth.title,
                auth_description=entry.auth.description,
                auth_headers=[
                    EntryHeaderRead(
                        name=h.name, label=h.label, description=h.description
                    )
                    for h in entry.auth.headers or []
                ],
                user_client=entry.auth.user_client,
                hosts=entry.hosts,
                server_host=_server_host(entry.url),
                sign_in_hosts=[
                    host for host in entry.hosts if host != _server_host(entry.url)
                ],
                homepage=entry.homepage,
                privacy_policy=entry.privacy_policy,
                about=entry.about,
                tools=entry.tools,
                added=entry.added,
                has_icon=icon_file(entry) is not None,
                connected=session.get(InstalledPlugin, entry.id) is not None,
            )
            for entry in current.document.entries
        ],
        removed=[
            RemovedEntryRead(id=item.id, reason=item.reason)
            for item in current.document.removed
        ],
    )


def _server_host(url: str) -> str:
    return urlsplit(url).hostname or ""
