"""A first-party entry as the screen lists it, and whether it is connected."""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.first_party.first_party_list import first_party_entries


class FirstPartyEntryRead(BaseModel):
    id: str
    name: str
    description: str
    author: str
    # `license` when it needs the SurfSense license; `free` otherwise.
    access: str
    hosts: list[str]
    connected: bool


def read_first_party(session: Session) -> list[FirstPartyEntryRead]:
    return [
        FirstPartyEntryRead(
            id=entry.id,
            name=entry.name,
            description=entry.description,
            author=entry.author,
            access=entry.access,
            hosts=entry.hosts,
            connected=session.get(InstalledPlugin, entry.id) is not None,
        )
        for entry in first_party_entries()
    ]
