import enum
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.db import Base, text_enum
from shared.secrets import decrypt, encrypt


class PluginKind(enum.StrEnum):
    REMOTE = "remote"


class PluginSource(enum.StrEnum):
    FIRST_PARTY = "first_party"
    REGISTRY = "registry"
    CUSTOM = "custom"


class ToolApproval(enum.StrEnum):
    ASK = "ask"
    ALWAYS = "always"


class ToolExposure(enum.StrEnum):
    DIRECT = "direct"
    DEFERRED = "deferred"


class InstalledPlugin(Base):
    """A plugin the user connected, the list entry it was connected from, and its sign-in.

    The sign-in sits on the row, as a connection's key does in `provider_connections`,
    encrypted; nothing that reads plugins for a screen or a model returns it.
    """

    __tablename__ = "installed_plugins"

    id: Mapped[str] = mapped_column(primary_key=True)
    kind: Mapped[PluginKind] = mapped_column(text_enum(PluginKind))
    source: Mapped[PluginSource] = mapped_column(text_enum(PluginSource))
    # One plugin per server, so a server's tools and key are never split across two.
    url: Mapped[str] = mapped_column(unique=True)
    publisher: Mapped[str]
    # The entry as listed at connect: name, auth, hosts, access. Kept so a plugin whose
    # entry later leaves its list still shows what it was.
    entry: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=True)
    connected_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # `token` now; OAuth's token set later. None when the server needs no sign-in.
    credential_kind: Mapped[str | None]
    credential_ciphertext: Mapped[bytes | None]

    @property
    def credential(self) -> str | None:
        if self.credential_ciphertext is None:
            return None
        return decrypt(self.credential_ciphertext)

    @credential.setter
    def credential(self, value: str | None) -> None:
        self.credential_ciphertext = None if value is None else encrypt(value)


class PluginTool(Base):
    """A tool a connected plugin offers, its switches, and how it last described itself."""

    __tablename__ = "plugin_tools"

    plugin_id: Mapped[str] = mapped_column(
        ForeignKey("installed_plugins.id", ondelete="CASCADE"), primary_key=True
    )
    tool: Mapped[str] = mapped_column(primary_key=True)
    # Where the server listed it, so tools keep the order their publisher chose.
    position: Mapped[int]
    title: Mapped[str | None]
    description: Mapped[str]
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSON)
    annotations: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=True)
    approval: Mapped[ToolApproval] = mapped_column(
        text_enum(ToolApproval), default=ToolApproval.ASK
    )
    exposure: Mapped[ToolExposure] = mapped_column(
        text_enum(ToolExposure), default=ToolExposure.DIRECT
    )
    first_seen_at: Mapped[datetime] = mapped_column(server_default=func.now())


class PluginSettings(Base):
    """One row: whether the user allowed third-party plugins."""

    __tablename__ = "plugin_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    third_party_on: Mapped[bool] = mapped_column(default=False)
