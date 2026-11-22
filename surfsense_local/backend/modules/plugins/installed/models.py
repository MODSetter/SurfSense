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


class ToolChange(enum.StrEnum):
    """Why a tool was switched off on its own: new since connect, or no longer as reviewed."""

    ADDED = "added"
    CHANGED = "changed"


class CheckFailure(enum.StrEnum):
    UNREACHABLE = "unreachable"
    SIGN_IN = "sign_in"
    # SurfSense's plugin host refused the license, for contract 2's reason.
    NEEDS_LICENSE = "needs_license"
    LICENSE_EXPIRED = "license_expired"
    LICENSE_REVOKED = "license_revoked"
    LICENSE_INVALID = "license_invalid"


# The plugin host's verdict on the license: only the host saying so sets or clears one.
LICENSE_FAILURES = frozenset(
    {
        CheckFailure.NEEDS_LICENSE,
        CheckFailure.LICENSE_EXPIRED,
        CheckFailure.LICENSE_REVOKED,
        CheckFailure.LICENSE_INVALID,
    }
)


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
    # The entry as listed at connect: name, auth, hosts, access. Kept so a plugin whose
    # entry later leaves its list still shows what it was.
    entry: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(default=True)
    connected_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # `token` or `license`; OAuth's token set later. None when the server needs no
    # sign-in. A license's key is read from the imported license, never stored here.
    credential_kind: Mapped[str | None]
    credential_ciphertext: Mapped[bytes | None]
    # When SurfSense last listed the server, and why that failed; None when it answered.
    checked_at: Mapped[datetime | None]
    check_failure: Mapped[CheckFailure | None] = mapped_column(text_enum(CheckFailure))
    # Set while the user has disconnected it: no sign-in, no tools offered, still listed.
    disconnected_at: Mapped[datetime | None]

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
    # Cleared once the user switches the tool back on.
    change: Mapped[ToolChange | None] = mapped_column(text_enum(ToolChange))


class PluginSettings(Base):
    """One row: whether the user allowed third-party plugins."""

    __tablename__ = "plugin_settings"
    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    third_party_on: Mapped[bool] = mapped_column(default=False)
