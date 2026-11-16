"""Uploads that are already text: the worker reads them off disk, not through Docling."""

TEXT_SUFFIXES = frozenset({".md", ".markdown", ".txt", ".text"})
