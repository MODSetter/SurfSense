"""Platform-native crawl/extraction actors (non-Apache-2; see ../LICENSE).

One subpackage per platform (e.g. ``youtube``), each a structured extractor for
that platform's data. Actors may reuse the shared fetch strategies in
``app.proprietary.web_crawler`` but expose their own platform-specific I/O.
"""
