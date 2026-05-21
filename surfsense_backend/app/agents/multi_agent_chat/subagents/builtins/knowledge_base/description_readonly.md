Read-only specialist for the user's workspace (documents and folders). Use to find, read, search, or quote a document or folder when your task needs workspace context — instead of asking the user or guessing.

Pass your full question as one string. The specialist runs in isolation: it cannot see this thread, so include any path hints, filters, or constraints it needs.

The specialist returns plain prose with absolute paths and `[citation:<chunk_id>]` markers when claims came from KB-indexed chunks. Preserve those markers verbatim if you forward the answer.
