# ADR 0088: The app draws Word and Excel files with one renderer

- **Status:** Accepted
- **Date:** 2026-11-05
- **Source:** the watermark bug, where a downloaded Word file showed a watermark the app did not (no permalink)

## Context

The Word viewer used docx-preview, which leaves VML text watermarks unparsed, hides picture watermarks behind the white page, does not paginate files without saved page breaks, and leaves charts and shapes blank. The Excel viewer kept only cell text. Whatever the agent makes must look in the app as it does when downloaded, and it can write almost anything into a file.

## Decision

- Studio's Word and Excel viewers and the agent's Word snapshot draw with `@silurus/ooxml`, pinned to an exact version, so the agent checks the pages the user sees. PowerPoint keeps pptx-renderer, which was not compared.
- It is the same for every user. Showing LibreOffice's PDF when Office support is on was rejected: most users would not have it, and a PDF drops comments.
- [`word-document/watermarks/`](../../surfsense_local/frontend/src/features/word-document/watermarks/) rewrites a copy of a file's VML watermarks before it is drawn, rather than forking the package: Word's 1 pt text is measured at 96 pt, a colour's theme slot is dropped, a shape type lacking `v:path` gets one, and Washout becomes DrawingML `lum`. The file a user downloads is never this copy.
- The parsers are inlined as data URLs: packaged, the app is on `file://`, where the library cannot fetch a `.wasm` beside it and the snapshot page's policy keeps the disk out of reach.
- The viewers lose the script-free frame. Pages draw to a canvas and the parser runs as WebAssembly, so nothing in a file becomes HTML; web links do nothing and no web font is asked for.

## Consequences

- Real and agent-made files were compared with LibreOffice, not Word, which was not available. An agent-made set is rendered through the real engine in CI, in [`agent-made-files/`](../../surfsense_local/frontend/src/features/word-document/agent-made-files/).
- A bump of the package can change the markup the rewrite relies on; those tests are what catches it. The rewrites belong upstream.
- A canvas exposes less to a screen reader than HTML did.
