# Sources from the web

**+ › Add from the web…** in the sources panel takes a web search or pasted links in one box, and shows what it found as rows. The user adds the rows they want, one at a time or all at once. Everything runs on the user's machine and their own connection, with no license, no plugin and no SurfSense server in the data path: a page's text is read with curl_cffi and trafilatura, a YouTube video's transcript with youtube-transcript-api, and a search goes to a SearXNG server, SurfSense's own unless the user names another. Every host asked is asked about first, as all egress is ([egress](egress.md)).

**Code:** [`surfsense_local/backend/modules/documents/web_sources/`](../../surfsense_local/backend/modules/documents/web_sources/), [`surfsense_local/frontend/src/features/sources/web/`](../../surfsense_local/frontend/src/features/sources/web/)
**Decisions:** [ADR 0068](../adr/0068-surfsense-calls-its-own-plugins-to-pull-a-link-into-sources.md), which the 1 Nov 2026 decision to retire the scraper plugins amends: its pullers moved into the app and its license gate went.

## Routes

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces/{workspace_id}/documents/web/search` | `{query, source, page}`: one page of the SearXNG server's results, `source` `web`, the default, or `youtube`; `page` 0 to 4 for Show more; `200` with `{results, more}`, each result `{url, title, description, site, puller}` |
| `POST` | `/workspaces/{workspace_id}/documents/web/open` | `{urls}`, 1 to 20 http(s) links: `200` with `{results, more: false}`, a row per link |
| `POST` | `/workspaces/{workspace_id}/documents/web` | `{urls}`, 1 to 20 http(s) links: a pending note per link, its pull queued; `201` with `created` and `duplicates` |
| `GET` | `/web-search/server` | `{url, default_url}`: the server the user named, or `null` for SurfSense's, `https://searxng.surfsense.com` |
| `PUT` | `/web-search/server` | `{url}`: an http(s) base address with no user name, password, query or fragment, kept without its trailing slash, or `null` for SurfSense's again; `422` otherwise. Nothing is contacted: the next search asks about the new host |

- **Search.** The server's JSON API is asked for `q`, `format=json`, `pageno` (the dialog's page plus one) and `categories=general`, with `Accept-Language: *` and `User-Agent: SurfSense`, since SearXNG's bot detection turns away a request without the first or with a library's name in the second ([`searxng.py`](../../surfsense_local/backend/modules/documents/web_sources/web_search/searxng.py)). A redirect may stay on the server's host only. Web links are kept, each once, in the server's order. A YouTube search asks for `<query> site:youtube.com` and keeps only video links. `more` is true while the server returned something and fewer than five pages were shown. The search waits in the request. Failures answer `502` with `{code, host, message}`: `search_unreachable` when the server does not answer, `search_failed` when it answers with no search, such as a `403` from a server whose `search.formats` lacks `json`, or an empty page every engine failed to fill.
- **Open.** Pasted links come back as rows titled by their own address, with no call: a preview would cost as much as the pull.
- **Add.** A link already in Sources, found by `$.source_url` across the workspace's notes wherever they were filed, comes back under `duplicates`, is not asked about and is not pulled again. Every other link becomes a `NOTE` at the top of the Library, `pending`, with no content and the link as its title, and `document_metadata` `{source_url, puller}`. One `pull_web_source` job is queued per note, and the request answers at once.
- **Asking first.** Before anything is written or sent, one question names every host the click reaches ([ADR 0060](../adr/0060-one-consent-question-per-user-action.md)): for Add, each link's own host, and `www.youtube.com` for a video; for a search, the server's host. A host not yet allowed is refused with `403 egress_disabled`, its `hosts` and `purpose` `web_page` or `web_search`, and recorded off so Settings › Network lists it; the app's prompt asks, then sends the request again. A loopback host, such as a SearXNG on `localhost`, needs no consent.

## Pullers

The link alone decides how it is read, whether it was pasted or picked from the results ([`links.py`](../../surfsense_local/backend/modules/documents/web_sources/links.py)). A note added by a puller this version retired, such as Reddit's, is read by whichever takes its link now. Each puller in [`pullers/`](../../surfsense_local/backend/modules/documents/web_sources/pullers/) says which links it takes, the hosts a read of one starts on, and how it reads one.

| Puller | Takes | Hosts asked about | Reads |
|---|---|---|---|
| YouTube | a video: `watch?v=`, `youtu.be`, `/shorts/`, `/embed/`, `/v/`, `/live/`, with an eleven-character id | `www.youtube.com`, whatever the link's host | the transcript and the video's facts |
| Web page | any other http(s) link, a YouTube channel or playlist included | the link's own | the page's main text |

**A page** ([`page_reading/`](../../surfsense_local/backend/modules/documents/web_sources/page_reading/)) is fetched with curl_cffi, impersonating Chrome's TLS and headers, with Google as its referer, as the hosted Web Crawl's static tier did. It never launches a browser: stealth browsers would not fit the installer, so a page only scripts build is not read.
- **Redirects** are followed by hand, at most ten hops. A hop to the same host is followed; a hop to another host is checked first, and one the user has not allowed fails the pull as moved, naming it, without contacting it. A public page may not send the read to `localhost` or a private address, where the app's own API answers.
- **What is read.** Only a text answer is downloaded, up to 20 MB: a PDF or another file is refused from its `Content-Type` before its bytes arrive. `text/plain` and `text/markdown` are kept as they are, titled by the file's name. HTML is decoded by the charset the server named, else as trafilatura detects it.
- **Extraction.** trafilatura keeps the main text as markdown, with tables, images and links, after Sphinx and MkDocs heading permalinks are dropped. When the page shows a currency amount the markdown lost, as pricing grids are dropped as boilerplate, extraction runs again favouring recall, then falls back to the whole body as markdown ([`lost_prices.py`](../../surfsense_local/backend/modules/documents/web_sources/page_reading/lost_prices.py)). The title is trafilatura's, else the link.
- **No text.** A Cloudflare or DataDome wall under 1,000 characters, a shell of 1 MB or more yielding under 2,500 characters, an empty extraction, a 404 or 410, and any other 4xx or 5xx are not a page.

**A video** ([`youtube_reading/`](../../surfsense_local/backend/modules/documents/web_sources/youtube_reading/)) is read with youtube-transcript-api, which asks `www.youtube.com` for the watch page, the player's answer and the chosen track. Its requests session refuses any other host, redirects included, and sets a 10-second connect and 30-second read limit the library leaves unset.
- **The track** is the one in the spoken language, which YouTube's own generated track names: a person's track in that language first, else YouTube's own; with no generated track, the first person's track. A translation is never asked for ([`transcript_tracks.py`](../../surfsense_local/backend/modules/documents/web_sources/youtube_reading/transcript_tracks.py)).
- **The source** opens with the video's title, then its channel, duration, link and transcript track as facts, then its description and the transcript, a caption per line with no timings and no caption repeated. The facts come from the player's answer the library already fetched; without them the title is the link.

## The pull

`pull_web_source` runs on the plugins queue, drained by its own sidecar, `worker-plugins`, with four threads that wait on the network. The single ingest thread stays free for indexing, so a slow page never holds back the user's own files ([`pull.py`](../../surfsense_local/backend/modules/documents/web_sources/background_pull/pull.py)):

1. **Start.** It marks the note `processing`, unless it was cancelled.
2. **Read.** The puller reads the link. Each host is checked again before it is contacted, in its own short transaction, and stamped as called for Settings › Network. A queued pull never asks: with a host turned off since the click, the pull fails and says so.
3. **Finish.** It writes the title and markdown and sets the note back to `pending`, unless a cancel came first. Then it queues the ordinary `ingest_document`, which takes the note to `ready` like any other.

Logs name the note, never the link: a session log can end up in an issue report.

A pull that fails marks the note `failed` with a sentence the panel shows ([`pull_failures.py`](../../surfsense_local/backend/modules/documents/web_sources/background_pull/pull_failures.py)):
- "This page couldn't be read. Open it in your browser, save it as a PDF, and add the file instead."
- "This page no longer exists at this link."
- "This link is a file, not a web page. Download it and add the file instead."
- "This link couldn't be reached. Check your connection and retry."
- "This page moved to … Retry to allow reading it there."
- "This video has no captions, so there is no transcript to add."
- "This video can't be read: it may be private, removed or age-restricted."
- "YouTube didn't share this video's transcript. Try again later."
- "Sending to … is off in Settings > Network."

**Retry and Cancel.** On a note that has no text yet, **Retry** queues the pull again, not only the indexing. Retry is the click a pull's hosts are asked about on: the link's, and the host a site moved the page to, which the failed pull keeps in `document_metadata.moved_to` and a later successful pull clears. **Cancel** revokes a queued pull. The plugins worker fails a pull it finds still `processing` when it starts, as an interrupted run.

## The dialog

[`add-from-web-dialog.tsx`](../../surfsense_local/frontend/src/features/sources/web/add-from-web-dialog.tsx) has one box, **Search the web or paste links**, over the rows it found. Enter submits and Shift+Enter starts a new line. The dialog keeps one height: the box stays put and the rows scroll beneath it. Before the first search, the space under the box offers Web and YouTube, one click each.

- **The box.** Text with a link in it opens the links, up to 20; anything else is a search where the pill under the text says: Web, the default, or YouTube. A link without `https://` counts when it starts with `www.` or has a path, such as `youtube.com/@name`, and every word on its line is a link, so a search like "node.js tutorial" stays a search. A line with no link is named back, and nothing is sent for it.
- **Rows.** Each row shows its title, led by a YouTube badge for a video, which comes with its transcript, then its whole link, then its description, its parts set apart by dots. The link shows whole on hover when cut off. A click asks first, in the app's link popup with the host and the whole address, then opens the page in the system browser. **Add** turns into "Added", or "Already in Sources" for a link added before. A search has **Show more** after its last row while it has more, and a row a later page repeats is shown once.
- **Add all.** It adds every row not yet added, 20 per request. The dialog stays open until **Close**, and the new sources appear in Sources at once.
- **Problems.** A server that does not answer, or answers with no search, is named with where to choose another; a question the user declined names every host still to allow.

**Settings › Network** holds the search server under the destinations ([`search-server-setting.tsx`](../../surfsense_local/frontend/src/features/sources/web/search-server-setting.tsx)): a field showing SurfSense's server as its placeholder, **Save**, and **Use SurfSense's** once another is named, with a note that the server must list `json` in its `search.formats`.

## Known gaps

- **Pages only scripts build are not read.** With no browser, a single-page app's shell, a bot wall or a page behind a login fails, and the sentence offers saving it as a PDF instead.
- **SurfSense's SearXNG server answered no search on 3 Nov 2026.** Every engine reported a proxy error, so each search on the default server fails as `search_failed` until its outgoing proxy is fixed. It also needs a rate limit per address before many apps rely on it.
- **A page moved to another host takes a Retry.** The pull cannot ask, so a redirect to a host not yet allowed, such as `example.com` to `www.example.com`, fails until the user retries and allows it.
- **Redirects are checked by host name.** A host whose name resolves to a private address is not refused as one written as that address is.
- **Every site added is a row in Settings › Network.** Consent is per host, so the list grows with each site read.
- **YouTube lists are not opened.** A channel, playlist or search link is read as a page, which rarely holds its videos.
- **Searches are not in the user's language.** `Accept-Language: *` leaves the language to the server's default.
- **No refresh.** A source cannot be refreshed from its link.
