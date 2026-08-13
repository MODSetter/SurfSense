"""Artifact generation: one pure executor per kind, wrapped by three doors.

The chat tool, the authenticated developer REST endpoint, and the anonymous
SEO-funnel endpoint are all thin adapters over the same executor. v1 ships
the image kind.
"""
