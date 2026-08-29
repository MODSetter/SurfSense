"""Input to ``WorkspaceRemotes.add``. Discriminant is ``provider``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RemoteProviderName = Literal["github", "gitlab"]


@dataclass(frozen=True)
class GithubSpec:
    provider: Literal["github"]
    url: str
    installation_id: str
    branch: str = "main"


@dataclass(frozen=True)
class GitlabSpec:
    provider: Literal["gitlab"]
    url: str
    token: str
    branch: str = "main"


RemoteSpec = GithubSpec | GitlabSpec
