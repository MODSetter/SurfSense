"""Mode-agnostic prompt fragments: header conventions + sandbox addendum."""

from __future__ import annotations

HEADER = """## Following Conventions

- Read files before editing — understand existing content before making changes.
- Mimic existing style, naming conventions, and patterns.
- Never claim a file was created/updated unless filesystem tool output confirms success.
- If a file write/edit fails, explicitly report the failure.
"""

SANDBOX_ADDENDUM = (
    "\n- execute_code: run Python code in an isolated sandbox."
    "\n\n## Code Execution"
    "\n\nUse execute_code whenever a task benefits from running code."
    " Never perform arithmetic manually."
    "\n\nDocuments here are XML-wrapped markdown, not raw data files."
    " To work with them programmatically, read the document first,"
    " extract the data, write it as a clean file (CSV, JSON, etc.),"
    " and then run your code against it."
)
