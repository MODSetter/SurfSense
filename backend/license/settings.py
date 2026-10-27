"""The license portal's settings, under surfsense_backend's names and meanings, so a deployment copies its values."""

import os
from collections.abc import Mapping


class LicenseSettings:
    def __init__(self, env: Mapping[str, str] = os.environ) -> None:
        self.KEYGEN_ACCOUNT_ID = env.get("KEYGEN_ACCOUNT_ID")
        # The admin token: without it the license routes are not served.
        self.KEYGEN_API_TOKEN = env.get("KEYGEN_API_TOKEN")
        # Self-hosted CE only; unset means Keygen Cloud.
        self.KEYGEN_API_URL = env.get("KEYGEN_API_URL", "").strip()
        self.KEYGEN_HOST = env.get("KEYGEN_HOST", "").strip()
        self.KEYGEN_POLICY_TRIAL = env.get("KEYGEN_POLICY_TRIAL")
        self.KEYGEN_POLICY_INDIVIDUAL = env.get("KEYGEN_POLICY_INDIVIDUAL")
        self.KEYGEN_POLICY_TEAM = env.get("KEYGEN_POLICY_TEAM")

        self.LICENSE_TRIAL_ENABLED = (
            env.get("LICENSE_TRIAL_ENABLED", "FALSE").upper() == "TRUE"
        )
        self.LICENSE_TRIAL_DAYS = int(env.get("LICENSE_TRIAL_DAYS", "14"))
        # ISO date; a trial issued before it expires that many days after it instead.
        self.LICENSE_TRIAL_EXPIRY_FLOOR = env.get(
            "LICENSE_TRIAL_EXPIRY_FLOOR", ""
        ).strip()
        self.LICENSE_DISPOSABLE_EMAIL_DOMAINS = env.get(
            "LICENSE_DISPOSABLE_EMAIL_DOMAINS", ""
        )

        # One resend is a Keygen check-out per license, so these also guard the Keygen quota.
        self.LICENSE_RATE_LIMIT_IP_PER_HOUR = int(
            env.get("LICENSE_RATE_LIMIT_IP_PER_HOUR", "10")
        )
        self.LICENSE_RESEND_RATE_LIMIT_PER_HOUR = int(
            env.get("LICENSE_RESEND_RATE_LIMIT_PER_HOUR", "5")
        )
        self.LICENSE_TRIAL_RATE_LIMIT_PER_HOUR = int(
            env.get("LICENSE_TRIAL_RATE_LIMIT_PER_HOUR", "3")
        )

        self.STRIPE_SECRET_KEY = env.get("STRIPE_SECRET_KEY")
        self.STRIPE_WEBHOOK_SECRET = env.get("STRIPE_WEBHOOK_SECRET")
        # A Payment Link carries no session metadata, so its price names the plan.
        self.STRIPE_PRICE_LICENSE_INDIVIDUAL = env.get(
            "STRIPE_PRICE_LICENSE_INDIVIDUAL", ""
        )
        self.STRIPE_PRICE_LICENSE_TEAM = env.get("STRIPE_PRICE_LICENSE_TEAM", "")

        self.SMTP_LICENSE_FROM = env.get("SMTP_LICENSE_FROM", "").strip()
        self.SMTP_LICENSE_REPLY_TO = env.get("SMTP_LICENSE_REPLY_TO", "").strip()

        self.POSTHOG_API_KEY = env.get("POSTHOG_API_KEY")
        self.POSTHOG_HOST = env.get("POSTHOG_HOST", "https://us.i.posthog.com")

        # The site the license pages are on; CORS lets it, its www or bare twin, and localhost in.
        self.NEXT_FRONTEND_URL = env.get(
            "NEXT_FRONTEND_URL", "https://www.surfsense.com"
        ).strip()
        # Shared by every copy of the backend; unset, each copy limits on its own.
        self.REDIS_URL = env.get("REDIS_URL")


config = LicenseSettings()
