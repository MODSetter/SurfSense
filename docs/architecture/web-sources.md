# Sources from the web

**+ › Add from the web…** in the sources panel takes a Google search or pasted links in one box, and shows what it found as rows. The user adds the rows they want, one at a time or all at once. A list link, such as a channel or a search page, opens into its items. SurfSense's own plugins do the pulling, with no agent and no thread. A YouTube link becomes the video's transcript and top comments, a Google Maps link the place and its reviews, a product link the product and its reviews, an Indeed link the job, and any other link the page's text. The feature needs a SurfSense license, and the plugin host judges it.

**Code:** [`surfsense_local/backend/modules/documents/web_sources/`](../../surfsense_local/backend/modules/documents/web_sources/), [`surfsense_local/frontend/src/features/sources/web/`](../../surfsense_local/frontend/src/features/sources/web/)
**Decisions:** [ADR 0068](../adr/0068-surfsense-calls-its-own-plugins-to-pull-a-link-into-sources.md)

## Routes

| Method | Path | Does |
|---|---|---|
| `POST` | `/workspaces/{workspace_id}/documents/web/search` | `{query, source, page}`: Google Search's `scrape` for `source` `web`, the default, or a site's own search, such as `youtube`; `page` 0 to 4 for Show more; `200` with one group of rows, each `{url, title, description, site, puller, fit}` |
| `POST` | `/workspaces/{workspace_id}/documents/web/open` | `{urls}`, 1 to 20 http(s) links: `200` with `groups` of rows, each `{link, results, more, failed}` |
| `POST` | `/workspaces/{workspace_id}/documents/web/list` | `{url, page}`, a list link and a page from 0 to 4: the next 20 of its items as one group |
| `POST` | `/workspaces/{workspace_id}/documents/web` | `{urls}`, 1 to 20 http(s) links: a pending note per link, its pull queued; `201` with `created`, `duplicates` and `rejected` |

- **Search.** On `web`, it keeps Google's organic results only, each link once: ads, related questions and the AI Overview are left out. Each result names the puller that would add it, and its `fit`: `one` to add, `list` to open, or `short_link`, which cannot be added. The search waits in the request: a results page can take up to three minutes when the plugin solves a captcha. Show more asks Google for one more results page and shows that page. On a site, the puller's `search` sends only the query to the plugin's own search parameter (YouTube's `search_queries`, Amazon's `search_terms`, TikTok's search page…), and the plugin's defaults choose the rest: Amazon's US store, Indeed's US site. Its items are read by the puller's listing and paged as a list link is. A site with no search of its own is refused with `422`.
- **Open.** Pasted single links come back together as one group with no `link`, each a row titled by its own address. No plugin is called for them: a preview would cost as much as the pull. Each list link is opened by its puller's plugin into its first 20 items, as its own group. The lists are read at once, after the license and consent are checked for each plugin. A list that cannot be read comes back `failed`, and the rest of the paste still opens. `more` says the list has items past these.
- **List.** Plugins take a count, not an offset, so page 2 asks for 60 items and returns the last 20. A list shows at most 100 items, the most several plugins return in one call.
- **Add.** A link already in Sources, found by `$.source_url` across the workspace's notes wherever they were filed, comes back under `duplicates` and is not pulled again. A list link or a short link comes back under `rejected`, with its `fit` as the reason: only one thing is added at a time. Every other link becomes a `NOTE` at the top of the Library, `pending`, with no content and the link as its title. Its `document_metadata` holds `source_url`, `puller` and `plugin_id`. One `pull_web_source` job is queued per note, and the request answers at once.
- **Refusals**, before anything is written or sent:
  - With no license imported: `403 {code: "license_refused", reason: "missing_license"}`, and nothing is asked of the network.
  - Without consent for `plugins.surfsense.com`: `403 egress_disabled`. The app's prompt asks, then sends the request again ([egress](egress.md)).
  - When the plugin host refuses the license, search answers `403 license_refused` with the host's `reason`: `expired`, `revoked` or `invalid`. An unreachable host is `502 plugin_unavailable`, and a tool error is `502 plugin_refused`.

## Pullers

The link alone decides which plugin pulls it, whether it was pasted or picked from the results ([`links.py`](../../surfsense_local/backend/modules/documents/web_sources/links.py)). Each puller is one file in [`pullers/`](../../surfsense_local/backend/modules/documents/web_sources/pullers/), and says three things:
- which links it takes;
- the tool calls it makes;
- how it writes the plugin's items as markdown;
- for a site with list links, how it lists one: the call, and how each item becomes a row.

| Puller | Takes as one source | Tool calls | Opens as a list |
|---|---|---|---|
| YouTube | `watch?v=`, `youtu.be`, `/shorts/`, `/embed/`, `/v/` | `scrape` with `download_subtitles`; `comments`, 100, top first, optional | channels, playlists, hashtags, searches, with `scrape` and `max_results` |
| TikTok | `/@user/video/<id>` | `scrape`; `comments`, 100, optional | profiles, hashtags, searches; `vm.` and `vt.tiktok.com` are short links |
| Google Maps | `/maps/place/`, `?cid=`, `maps.app.goo.gl` | `scrape` with `include_details` and `max_reviews` 100 | searches, with `max_places` |
| Amazon | `/dp/`, `/gp/product/`, `?asin=`, `a.co`, `amzn.to`, `amzn.eu` | `scrape` with `include_details` | searches, categories, best sellers, as cards without details |
| Walmart | `/ip/` | `scrape` with `include_details`; `reviews`, 100, most helpful, optional | searches, categories, as cards without details |
| Indeed | any link with `jk` | `scrape` with `scrape_job_details` | searches and company pages, as cards without details |
| Web Crawl | any other http(s) link | `crawl`, depth 0, one page, no links, up to 1,000,000 characters | nothing |

Every item a list returns routes back to its puller as one source: a video's `watch?v=`, a place's `/maps/place/`, a product's `/dp/` or `/ip/`, a job's `viewjob?jk=`.

Every source opens with its title, then its facts as a list, then a section for each part, such as Description, Transcript, Comments or Reviews. A part with nothing in it is left out. A YouTube transcript is the person-written track when there is one, read from its SRT without cue numbers, timings or repeated captions. Walmart's HTML description is read as text. The items come from the result's `structured_content`, which holds them whole; the text projection is cut at 32 KB.

## The pull

`pull_web_source` runs on the plugins queue, drained by its own sidecar, `worker-plugins`, with four threads that wait on the network. The single ingest thread stays free for indexing, so a slow pull never holds back the user's own files ([`pull.py`](../../surfsense_local/backend/modules/documents/web_sources/background_pull/pull.py)):

1. **Start.** It marks the note `processing`, unless it was cancelled.
2. **Check again.** It checks the license key and the plugin host's consent a second time, and records the call for Settings › Network. A queued pull never asks: with the host turned off since the click, the pull fails and says so.
3. **Call.** It runs the puller's tool calls at once, through `McpSession.call_tool`, with a ten-minute read limit per call and no retry. An optional call that fails, such as comments that are turned off, leaves its part out.
4. **Finish.** It writes the title and markdown and sets the note back to `pending`, unless a cancel came first. Then it queues the ordinary `ingest_document`, which takes the note to `ready` like any other.

A pull that fails marks the note `failed` with a sentence the panel shows:
- "This link couldn't be read."
- "Pulling links needs a SurfSense license."
- "Your SurfSense license has expired."
- "SurfSense's plugins couldn't be reached."
- "Sending to … is off in Settings > Network."

**Retry and Cancel.** On a note that has no text yet, **Retry** queues the pull again, not only the indexing, and **Cancel** revokes a queued pull. The plugins worker fails a pull it finds still `processing` when it starts, as an interrupted run.

## The dialog

[`add-from-web-dialog.tsx`](../../surfsense_local/frontend/src/features/sources/web/add-from-web-dialog.tsx) has one box, **Search Google or paste links**, over the rows it found. Enter submits and Shift+Enter starts a new line. The dialog keeps one height: the box stays put and the rows scroll beneath it. Before the first search, the space under the box offers every site, one click each.

- **The box.** Text with a link in it opens the links, up to 20; anything else is a search on the site chosen in the menu under the text: Google Search, the default, YouTube, TikTok, Google Maps, Amazon, Walmart or Indeed. Pasted links open by their own site whatever is chosen, and a new dialog starts on Google Search. Links can be one per line or several on a line. A link without `https://` counts when it starts with `www.` or has a path, such as `youtube.com/@name`, and every word on its line is a link, so a search like "node.js tutorial" stays a search. A line with no link is named back, and nothing is sent for it.
- **Rows.** Each row shows its title, its site and, for a site with its own puller, a badge naming it, such as YouTube.
  - A row to add has **Add**, which turns into "Added", or "Already in Sources" for a link added before.
  - A list row has **Open**, which shows its items in a panel beneath that row, headed by the list's name, its badge and how many items it shows. A pasted list link gets the same panel, named by its link.
  - A short link says why it can't be added.
  - A list group has **Show more** while the list has more.
- **Add all.** It adds every row not yet added, 20 per request. The dialog stays open until **Close**, and the new sources appear in Sources at once.
- **Licence offer.** With no license, or an expired one, as `GET /license/status` reports, the dialog opens on an offer instead of the search: **Start a free trial** and **License settings**. A refusal from the plugin host on the way shows the same offer, with the host's reason.

## Known gaps

- **TikTok short links.** `vm.tiktok.com` and `vt.tiktok.com` are refused. Following them would need a consent beyond the plugin host's.
- **Reddit and Instagram** have no puller. Their plugins are not listed ([plugin host](plugin-host.md#known-gaps)), so their links are read by Web Crawl as pages.
- **Amazon reviews.** An Amazon source holds only the reviews on the product page: the plugin takes no count of them.
- **Transcript language.** The YouTube pull asks the plugin for English subtitles, its default, so a video without an English track, such as a French one, has no transcript. The source should hold the original-language transcript: a person-written track in the spoken language, else the auto-generated one, never a translation. That needs an `original` mode in the YouTube plugin (`subtitles_language`), with no translation call for it. The plugin host must ship that mode before the app sends it.
- **YouTube live links.** A `/live/<id>` link is opened as a list, which the plugin cannot read, so its group comes back failed.
- **List pages cost more each time.** Page 2 of a list reads 60 items to show the last 20, since plugins take a count, not an offset. A list that changes between pages shifts: the dialog drops an item it already shows, but an item that moved back past a page is never shown. Plugins that take the site's own next-page token would fix both.
- **Site searches use the plugins' defaults.** Amazon searches its US store and Indeed its US site, since only the query is sent. A place belongs in the query, "cafes in Kinshasa"; there is no region or place field.
- **No refresh.** A source cannot be refreshed from its link.
