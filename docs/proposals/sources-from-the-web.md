---
status: proposed
code:
  - surfsense_local/backend/modules/documents/web_sources/
  - surfsense_local/backend/modules/plugins/remote/mcp_client/
  - surfsense_local/backend/worker/consumer.py
  - surfsense_local/frontend/src/features/sources/
  - surfsense_local/frontend/src/features/dashboard/
---

# Sources from the web

> Beside **Upload files…** and **Upload folder…**, the add menu gets **Add from the web…**. It searches Google, or takes pasted links, and turns each picked link into a source. SurfSense's own plugins do the pulling: a YouTube link becomes the video's transcript and comments, a Google Maps link the place and its reviews, any other page its text. It needs an active license. Without one, the dialog asks the user to activate one.

Gemini Notebook, formerly NotebookLM, adds sources this way: a search box for the web, and links pasted in. SurfSense's scraper plugins can already read Google, any web page, YouTube, TikTok, Google Maps, Amazon, Walmart and Indeed ([plugins](../architecture/plugins.md), [plugin host](../architecture/plugin-host.md)). Today their results reach Sources only when the agent calls one in a thread and the user saves the step ([agent](../architecture/agent.md)). This feature reaches them without a thread or a model. It is the first license-only feature outside the agent.

## What changes

| | Today | With this |
|---|---|---|
| Add menu | Upload files, Upload folder, New folder, New note | adds **Add from the web…**, after Upload folder |
| A web page as a source | save it as a file, then upload it | search or paste its link |
| A YouTube video, Maps place, product or job as a source | a plugin in a thread, then **Save to Sources** | paste its link |
| Who calls a plugin's tool | the agent's runtime only | also the API, for this feature |
| License | unlocks plugins in the agent | also unlocks this feature |

## The dialog

- **Search.** A query box. **Search** returns one page of Google results, about ten: organic results only, without ads, related questions or the AI Overview, and each link once. Each row shows the title, the site and the snippet, with a checkbox. Rows are labelled with the plugin that will pull them, for example "YouTube", so a user knows a video will come with its transcript.
- **Paste links.** A box that takes links one per line, up to 20 per **Add**. Links that are not http(s), and links no puller takes (see [Links](#links)), are named under the box and are not sent.
- **Add** sends the ticked and pasted links together and closes the dialog. Each link appears at once in Sources as a processing row, as an upload does.
- **Without a license**, the dialog body is the activation prompt: **Start a free trial** and **License settings**, from the license feature. It is shown before anything is typed when the app has no license, and in place of results when the plugin host refuses the license.
- **The network question.** The first **Search** or **Add** asks the one consent for `plugins.surfsense.com`, through the app's existing prompt ([egress](../architecture/egress.md)). One consent covers every plugin.

## Links

The link alone decides which plugin pulls it, whether it was pasted or picked from the search results. The search is always Google's. A YouTube result that is picked is pulled by YouTube.

| Link | Puller | Tool calls | The source holds |
|---|---|---|---|
| YouTube video, short (`watch?v=`, `youtu.be`, `/shorts/`) | YouTube | `scrape` with `download_subtitles`; `comments`, 100, top first | title, channel, date, duration, views; description; transcript, the SRT text without its timings; top 100 comments with author and likes |
| TikTok video (`/@user/video/<id>`) | TikTok | `scrape`; `comments`, 100 | caption, author, date, plays and likes, hashtags; top 100 comments |
| Google Maps place (`/maps/place/`, `?cid=`, `maps.app.goo.gl`) | Google Maps | `scrape` with `include_details`, `max_reviews` 100 | name, category, address, phone, website, rating and its spread, opening hours; 100 reviews with stars, date and the owner's reply |
| Amazon product (`/dp/`, `/gp/product/`, `a.co`, `amzn.to`) | Amazon | `scrape` with `include_details` | title, brand, price, rating, features, description, overview, the review summary; the reviews on the product page, since the plugin reads no more |
| Walmart product (`/ip/`) | Walmart | `scrape` with `include_details`; `reviews`, 100, most helpful | name, brand, price, rating, description, specifications; 100 reviews |
| Indeed job (`/viewjob?jk=`) | Indeed | `scrape` with `scrape_job_details` | title, company, location, pay, job type, benefits, description |
| Any other http(s) link | Web Crawl | `crawl`, depth 0, no links, up to 1,000,000 characters | the page's text as markdown |

- **One link, one thing.** A platform link that names a list is refused in the dialog with a sentence saying so: a channel, playlist, profile, hashtag, search page, category or company page. Pulling a channel into many sources is a later step.
- **Short links the plugin cannot follow are refused.** `vm.tiktok.com` and `vt.tiktok.com` would need the app to call TikTok first, which is a host outside the one consent. The dialog asks for the full link instead.
- **Reddit and Instagram** have no puller yet. Their plugins are written but left out of the list until they can read anonymously ([plugin host](../architecture/plugin-host.md#known-gaps)). Until then their links go to Web Crawl like any page.
- Each puller is one file with three parts: the links it takes, the tool calls it makes, and how it writes the plugin's items as markdown. The items are read from the result's `structured_content`, which holds them whole. The text projection is cut at 32 KB.

## Decisions

- **The API calls the plugins, with no agent.** A pull is the user's own action in Sources, not a model's choice, so it skips the turn, the gateway and the tool approvals. `mcp_client/session.py` gains `call_tool` beside `list_tools`, on the same SDK client and the same error translation. It is never retried, since a call may have done its work before it failed. This ends "SurfSense lists a server's tools itself … it never calls one" ([plugins](../architecture/plugins.md)), so it gets its own ADR. The agent's path does not change.
- **The license is the only gate.** No plugin needs to be connected in Settings › Plugins, and pausing one there does not affect this feature. The API reads the license key when it calls and sends it only to the plugin host, as it does for a connected plugin. With no license imported, the request is refused before any network question, with `403 license_refused`. With one, the plugin host judges it ([license](../architecture/license/app.md)). A `401` or `403` from the host comes back as `license_refused` with the host's `reason`: `missing_license`, `expired`, `revoked` or `invalid`.
- **Pulling runs in the background.** `POST /workspaces/{id}/documents/web` checks the license and the consent, skips links already in Sources, and creates one pending note per link with no content and the link as its title. It then queues one pull per note and answers `201` with `created`, `duplicates` and `rejected`, as an upload answers.
- **Pulls run on the plugins queue, not the ingest queue.** The ingest queue has one worker, because indexing saturates the CPU. The plugins queue has four, because its jobs wait on the network ([`consumer.py`](../../surfsense_local/backend/worker/consumer.py)). A pull that takes minutes, such as a video's comments or a place's reviews, never holds an upload back. When the pull succeeds, the job writes the title and markdown and queues the existing `ingest_document`. When it fails, the note is marked failed with a sentence the user can read: the license was refused, the site could not be read, or SurfSense's plugins could not be reached.
- **Consent is asked on the click, and checked again in the job.** The question is asked only on the user's action ([ADR 0017](../adr/0017-egress-off-by-default.md), [ADR 0060](../adr/0060-one-consent-question-per-user-action.md)). If the user turns the host off before a queued pull runs, the pull fails and says so. The job never asks.
- **A source is a note with its link.** It uses the existing `NOTE` type, with no migration. Its `document_metadata` holds `source_url`, `puller`, `plugin_id` and `fetched_at`, as **Save to Sources** stores a plugin step. The user can edit it like any note.
- **A link already in Sources is skipped.** It is found by `$.source_url` across the workspace's notes, wherever the note was filed since. It comes back under `duplicates`, and the toast says the link was already there. It is not pulled again.
- **Sources land at the top of the Library**, as a saved plugin step does.
- **Retry pulls again.** For a note that has no content yet, **Retry** queues the pull, not only the indexing. **Cancel** revokes a queued pull. A pull killed with the worker is failed when the plugins worker starts, as an interrupted plugin run is.
- **Search waits in the dialog.** `POST /workspaces/{id}/documents/web/search` answers with the results. A Google results page can take up to three minutes when the plugin has to solve a captcha. The dialog shows the wait, and closing it cancels the request.

## Not decided here

- Reddit and Instagram pullers, once their plugins are listed again.
- A **Web / YouTube** switch beside the search box, to search with the YouTube plugin instead of Google.
- A list link, such as a channel or a playlist, as many sources.
- Refreshing a source from its link.
- Following short links on hosts other than the plugin host.
- Crawling a whole site into sources.

## Checks

- **API tests**, against a stand-in plugin host on loopback, as `test_first_party_plugins.py` runs one:
  - the license key reaches the host and goes nowhere else;
  - no license refuses the request before any network question;
  - a refused license comes back with its reason;
  - without consent, nothing is sent;
  - each puller's tool calls, with their arguments;
  - each puller's markdown, from recorded items;
  - duplicates are skipped;
  - failed pulls carry a readable sentence;
  - Retry and Cancel act on a pull.
- **Frontend tests**, in `features/sources`:
  - the menu item;
  - search, tick and add;
  - pasted links, and the refused ones named;
  - the activation prompt without a license;
  - the rows that appear as processing.
- **Manual**, with a license on the real plugin host: one link per puller, plus a page Web Crawl reads, a link already added, and the same with no license.
