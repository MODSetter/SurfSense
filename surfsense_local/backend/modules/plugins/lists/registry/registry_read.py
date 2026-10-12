"""The registry as Settings > Plugins lists it: each entry, its publisher, and whether it is connected."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.registry.current_registry import CurrentRegistry
from modules.plugins.lists.registry.registry_icons import icon_file

PARTNER = "partner"


class RegistryEntryRead(BaseModel):
    id: str
    name: str
    description: str
    author: str
    # `partner` or `community`; a partner's listing is shown as verified.
    publisher: str
    verified: bool
    access: str
    access_note: str | None
    # `none`, `token` or `oauth`; a token entry says what key to paste.
    auth_type: str
    auth_title: str | None
    auth_description: str | None
    hosts: list[str]
    homepage: str | None
    privacy_policy: str | None
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
                publisher=entry.publisher,
                verified=entry.publisher == PARTNER,
                access=entry.access,
                access_note=entry.access_note,
                auth_type=entry.auth.type,
                auth_title=entry.auth.title,
                auth_description=entry.auth.description,
                hosts=entry.hosts,
                homepage=entry.homepage,
                privacy_policy=entry.privacy_policy,
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
