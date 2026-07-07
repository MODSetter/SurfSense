"""App-wide crawler block classification (Apache-2.0, generic).

Phase 3e (Slice A). Mirrors ``app/utils/proxy`` and ``app/utils/captcha``: this
package holds only the **generic, vendor-agnostic** glue — here, a pure block
classifier (passive telemetry from public anti-bot markers). It is consumed by
the separately licensed proprietary crawler to label ``CrawlOutcome.block_type``.

The **bypass-specific tuning** (the stealth kwargs builder / geoip coherence, and
the deferred WebGL spoof + humanize choreography) is NOT generic and lives under
the proprietary boundary in ``app/proprietary/web_crawler/`` (``stealth.py``).
"""

from app.utils.crawl.classifier import BlockType, classify_block
from app.utils.crawl.contacts import Contacts, extract_contacts, is_social_host

__all__ = [
    "BlockType",
    "Contacts",
    "classify_block",
    "extract_contacts",
    "is_social_host",
]
