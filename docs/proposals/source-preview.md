---
status: proposed
tracking: https://github.com/MODSetter/SurfSense/issues/2077
code:
  - surfsense_local/backend/modules/documents/schemas.py
  - surfsense_local/frontend/src/features/file-viewers/
  - surfsense_local/frontend/src/features/source-preview/
  - surfsense_local/frontend/src/features/sources/
  - surfsense_local/frontend/src/features/dashboard/
---

# Previewing a source in the app

> Clicking a source opens its original file in a panel that slides out beside the sidebar, when the app has a viewer for that file type. PDF is the first. Every other type opens in the operating system's app, as every type does today. Each viewer added later moves one more type into the panel.

Today a source's title and its **Open** item both hand the file to the operating system ([`documents.md`](../architecture/documents.md), The original file). The app already renders PDF, DOCX, XLSX, PPTX, HTML and images, but only for Studio artifacts ([`studio.md`](../architecture/studio.md), Viewers). The idea and its duplicate check are in [#2077](https://github.com/MODSetter/SurfSense/issues/2077).

## What changes

| | Today | With this |
|---|---|---|
| Click a source's title | opens the file in the OS app | a type with a viewer opens the preview panel; any other type opens in the OS app |
| Row menu | Open, Show in folder, Retry, Cancel, Delete | adds **Preview**, only for a type with a viewer |
| Viewers | Studio's, keyed by format, fed an `ArtifactDetail` | Studio's unchanged; a second registry for sources, keyed by MIME type, fed a file URL |
| `DocumentRead` | no file type | `mime_type`, `null` unless the row is a `FILE` |

## Decisions

- **A click opens the original, always.** Where it opens depends only on whether the registry has a viewer for the file's MIME type. There is no fallback viewer: extracted text is what the AI reads, not the user's file, and a "can't preview" card would be a dead end one click from the OS app that does open it.
- **Citations and artifacts are not touched.** The citation panel, the artifact panel, the Studio panel and Studio's viewers and registry keep their code and their behaviour. The only thing that reaches the right panel is that it collapses while the preview is open, and its content is kept for when it comes back.
- **PDF first.** The rest follow one type per change, each ported from its Studio viewer. A type moves into the panel only once its viewer works on a source, so nothing that opens today gets worse.
- **The panel is a second rail, not a wider sidebar.** `SlideRail side="start"` ([`slide-rail.tsx`](../../surfsense_local/frontend/src/components/ui/slide-rail.tsx)) sits between the sidebar and the chat, so it opens with the same 240 ms width tween as the right panel, and the source list stays visible to click the next one.
- **Width.** The default window is 1280 px, which leaves 1216 px for the workspace. The sidebar takes 272 and the chat keeps at least 520, so the preview gets 400 px (`MAIN_RAIL_WIDTH`), with the PDF fitted to that width. While it is open the right panel collapses without writing its saved preference, and comes back when the preview closes.
- **The preview is remembered per workspace**, as the right panel remembers being open: `surfsense:source-preview:v1` in `localStorage` maps a workspace id to the open document id, beside `surfsense:right-panel:v1` ([`chrome-prefs.ts`](../../surfsense_local/frontend/src/features/dashboard/chrome-prefs.ts)). Closing the preview clears the entry. A remembered document that is gone or has no viewer any more is dropped and the rail stays shut. Restoring it collapses the right panel as opening it does.
- **Any status previews.** Upload writes the file into the document's folder before the row is committed ([`router.py`](../../surfsense_local/backend/modules/documents/router.py)), so a pending, processing or failed source has its original. Seeing it is how a user judges why a parse failed.
- **`mime_type` comes from the stored metadata, only for `FILE`.** Upload and cloud import both write the server-validated type into `document_metadata` (`validate_upload` in [`storage.py`](../../surfsense_local/backend/modules/documents/storage.py)), and have since `v2.0.0`, so existing rows need no migration or backfill. A note's metadata is whatever the client sent, so a note claiming `application/pdf` would look previewable and then `404` on `/original`; the field is `null` for anything but `FILE`.
- **The bytes come from `GET .../documents/{id}/original`,** which exists and is unused by the frontend. It stays an attachment, since `fetch` ignores `Content-Disposition`, so an HTML source cannot run on the API's origin when its viewer arrives.

## What a click does

| Where | Does |
|---|---|
| Title, type with a viewer | opens the preview; the open source again closes it; another source switches it |
| Title, any other type | opens the file in the OS app, as today |
| Title, `NOTE` | nothing, as today |
| Checkbox | selects the source for chat, as today |
| Menu: Preview | same as the title, shown only for a type with a viewer |
| Menu: Open, Show in folder | the OS app and the file manager, as today |
| Menu: Delete | as today, and closes the preview if it shows that source |
| Preview header | title, Open, Show in folder, close; the PDF's zoom controls portal into it |
| Switching workspace | shows that workspace's remembered preview, or none |
| Restarting the app | reopens the active workspace's remembered preview |

## Seams

- **`features/file-viewers/`** holds the MIME-keyed registry: `getFileViewer(mimeType)` returns a viewer or `null`. A viewer takes `{ url, mimeType, sizeBytes, title, actionsContainer }` and fetches its own bytes. Its PDF viewer is ported from Studio's, as Studio's was ported from the web app's, without Studio's `ArtifactDetail` prop.
- **Studio keeps its own viewers.** Pointing Studio at the shared registry would remove the copy, but it changes the artifact panel, so it is a later refactor with its own issue, not part of this work.
- **`features/source-preview/`** owns the rail, the header and the click rule. The dashboard owns only whether the rail is open and which document it shows, as it owns `inspect` for the right panel.

## Work, as sub-issues of #2077

1. `mime_type` on `DocumentRead` and `WorkspaceDocument`; the MIME-keyed registry with its PDF viewer; the preview rail and its per-workspace memory; the click rule and the **Preview** menu item.
2. One per type, each moving it into the panel: DOCX, XLSX, PPTX, HTML, images. Each checks its viewer's size limit against the source, as DOCX and XLSX cap at 15 MB today.
3. CSV, MD and TXT, which have no Studio viewer yet.

The change that completes the first step updates [`documents.md`](../architecture/documents.md): the desktop app previews an original whose type it has a viewer for and opens the rest natively.

## Not in scope

- Any change to citations: a citation keeps opening the citation panel on the right. Opening the preview at a cited page would also need a mapping, since chunks carry line ranges of the extracted markdown, not PDF pages.
- Any change to the artifact panel, the Studio panel or Studio's viewers, including moving them onto the shared registry.
- A preview wider than 400 px on a larger window, or a resizable rail. `SlideRail` takes one fixed width.
- Previewing notes. A note has no file behind it.
