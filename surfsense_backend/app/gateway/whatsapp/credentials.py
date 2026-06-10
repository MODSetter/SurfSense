"""Credential helpers for WhatsApp gateway accounts."""

from __future__ import annotations

from typing import TypedDict

from app.config import config


class WhatsAppCredentials(TypedDict, total=False):
    business_token: str
    waba_id: str
    phone_number_id: str
    business_id: str
    registration_pin: str
    api_version: str


def load_system_whatsapp_credentials() -> WhatsAppCredentials:
    if not (
        config.WHATSAPP_SHARED_BUSINESS_TOKEN and config.WHATSAPP_SHARED_PHONE_NUMBER_ID
    ):
        raise RuntimeError("whatsapp_system_credentials_not_configured")

    return {
        "business_token": config.WHATSAPP_SHARED_BUSINESS_TOKEN,
        "phone_number_id": config.WHATSAPP_SHARED_PHONE_NUMBER_ID,
        "waba_id": config.WHATSAPP_SHARED_WABA_ID,
        "api_version": config.WHATSAPP_GRAPH_API_VERSION,
    }
