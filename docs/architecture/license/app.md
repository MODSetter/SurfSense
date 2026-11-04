# License in the desktop app

The desktop app imports a Keygen license file and verifies it offline, against Ed25519 public keys compiled into the binary, and never contacts Keygen. A license unlocks SurfSense's paid plugins and priority support, and a trial the same for its term; a Business license, sold per person, and the Business trial also name the job plugins they unlock. In the app a license changes only what Settings and the sidebar show, and its key is sent to SurfSense's plugins and, to fetch a renewed file, to SurfSense's license server. No state of the license ever disables the app. The check on the machine is honesty for the interface, not enforcement: the app is public and can be rebuilt without it, so enforcement belongs to the servers a paid plugin calls.

**Code:** [`surfsense_local/backend/modules/license/`](../../../surfsense_local/backend/modules/license/), [`surfsense_local/frontend/src/features/license/`](../../../surfsense_local/frontend/src/features/license/)
**Decisions:** [ADR 0019](../../adr/0019-offline-licenses.md), ADR 0079 for Business; [ADR 0017](../../adr/0017-egress-off-by-default.md) and [ADR 0060](../../adr/0060-one-consent-question-per-user-action.md) for the renewal's consent

The file format is [contract 1](../../contracts/01-license-file.md); the hosted side that issues files, and answers a renewal, is the [portal](portal.md).

## What the license gates

Paid plugins and priority support, nothing else: priority support is offered in the license email. Expiry stops those two and leaves the app, its data and its updates alone. Updates are free for everyone and the updater has no license logic: with public installers, an expired user could delete the license file and become a free user, so gating updates would be theater. `maxUsers`, a team's seats or a Business license's people, is shown, never enforced.

A Business license, and the Business trial, which is a `trial` carrying jobs, also list the job plugins they unlock, as Keygen entitlement codes such as `JOB_QUESTIONNAIRE`. The status reports them with the firm the checkout named; what a job plugin needs to run is its own check ([ADR 0067](../../adr/0067-b2b-jobs-ship-as-paid-plugins.md)).

SurfSense's paid plugins run on its plugin host, and the app sends every request to them the imported key as `Authorization: License <key>`, without checking its expiry ([plugins](../plugins.md#surfsenses-own-plugins)); the host checks it with Keygen on every call ([plugin host](../plugin-host.md#the-license-check)). Importing, replacing or removing a license asks the plugin host straight away whether it unlocks them, and so does a renewal fetched from Settings, so Settings › Plugins, `@` and the agent follow at once ([plugins](../plugins.md#the-license-verdict)). A file the [daily check](#the-daily-check) imports reaches them at the next stale verdict instead: the next agent turn or visit to Settings › Plugins once the last verdict is five minutes old. Inside the app, Settings and the sidebar are what read the license state.

## Verifying a file

`verify()` in `verify.py` follows contract 1's consumer steps in order and stops at the first failure:

1. Strip the PEM markers and whitespace and base64-decode the JSON; anything unreadable is `not_a_license_file`.
2. An `alg` other than `base64+ed25519` is `unsupported_algorithm`.
3. The signature over `"license/" + enc` must verify with one of the compiled keys, or the file is `bad_signature`. `enc` is not decoded until this passes.
4. `meta.issued` more than `MAX_CLOCK_DRIFT`, five minutes, in the future is `clock_untrusted`; a non-null `meta.expiry` in the past is `file_expired`. The portal checks files out with `meta.expiry: null`.

The five minutes are there because a laptop clock running a few minutes fast is not tampering. A passing file yields its key, plan, email, license expiry, `maxUsers`, `meta.issued` and `meta.expiry`, and two fields only some files carry: `metadata.firm`, trimmed, with a blank one read as none, and `metadata.jobs`, split on its commas and trimmed, an empty list when absent. `PUT /license` answers a rejection with 422 and `{code, message}`; the messages are in `router.py`.

`verify_signature()` is steps 1 to 3 plus the decode; `verify()` adds step 4 and is what import runs. A status read of a stored file runs only `verify_signature()`: the time checks were passed when the file was imported, and from then on the clock is the watermark's business (below). The file TTL is not re-checked on a read either, since the portal always issues `meta.expiry: null` (contract 1); import still refuses a file whose TTL has lapsed. The other three rejections stay errors on a read: a stored file passed the same three checks at import and the key list only grows, so they can only mean the row was edited by hand, which is corruption to notice rather than a state to show.

`KEYGEN_PUBLIC_KEYS_HEX` is a tuple, newest first, and a file signed by any key in it is accepted. Rotating the Keygen account key is therefore a release that trusts both keys, not a recall of every license already issued. The keys are source code, never read from configuration, environment or disk; tests swap in the fixture key by patching the constant.

## State

The singleton row `license_state` holds the file as imported, when it was imported, and `clock_watermark`. The state is re-derived from the stored file on every read:

| State | When |
|---|---|
| `none` | no file is stored |
| `active` | the license expiry is in the future |
| `license_expired` | the license expiry has passed; the file stays stored and shown |
| `clock_untrusted` | the clock is more than five minutes behind the watermark, which includes the stored file's `meta.issued`, whatever the expiry |

Every import, and every status read of a stored file whose signature verifies, moves the watermark to `max(watermark, now, meta.issued)`. A clock wound back, or behind the time the stored file was issued, therefore reads as `clock_untrusted` until time catches up, instead of reviving an expiring license or failing the read. The watermark lives in SQLite the user can edit, so a `ponytail:` comment calls it honesty for the UI, not enforcement.

There is one slot: importing a valid file replaces whatever was stored. That is what contract 1's rule 7 needs, since a resend checks out a fresh file for the same license with a later `meta.issued`, and a renewal one with a later expiry too, and it takes the old one's place.

| Route | Does |
|---|---|
| `GET /license/status` | answers `state`, `plan`, `email`, `expiry`, `max_users`, `firm` (null when the file names none) and `jobs` (a list, empty when it names none) |
| `PUT /license` | verifies `{certificate}`, stores it and answers the new status |
| `POST /license/refresh` | fetches the stored license's current file from the license server, imports it and answers the new status ([renewal](#renewal)) |
| `DELETE /license` | forgets the file; the state returns to `none` |

## Renewal

A Business license renews every year on the same key: the license server moves its expiry, the end of the period paid for plus 30 days, and answers a fresh file for the key ([contract 1](../../contracts/01-license-file.md), producer rule 7). The app fetches that file two ways, both through `refresh_license()` in [`renewal/license_refresh.py`](../../../surfsense_local/backend/modules/license/renewal/license_refresh.py): when the user checks for a renewal in Settings, `POST /license/refresh`, and, around a Business license's end, on its own once a day ([below](#the-daily-check)). An offline machine imports the emailed file like any other.

The license server is `https://api.surfsense.com`, compiled into `renewal/license_server.py`; `SURFSENSE_LOCAL_LICENSE_SERVER_URL` points a developer's build, or a firm's mirror, at another. `plugins.surfsense.com` serves the same routes today, but it is the plugin host's name, under the plugin host's consent. A refresh, in order:

1. With no license stored, it stops at `license_none` and sends nothing.
2. The server's host must be allowed in Settings › Network ([egress](../egress.md)). `host:api.surfsense.com` is built in, off until the user allows it. Refused, it stops at `refresh_egress_blocked` and sends nothing; the route's 403 carries the `destination`, `host`, `hosts` and `purpose` (`license_refresh`) an `egress_disabled` refusal carries. Settings' check turns it into the consent question, through `askEgress()` in [`use-license-refresh.ts`](../../../surfsense_local/frontend/src/features/license/use-license-refresh.ts), and checks once more on Allow; the question says that allowing also lets the daily check reach the host, which no dialog can ask about later ([egress](../egress.md#asking-for-consent)). Cancel leaves the refusal's message, which names the host to allow. A mirror's host is recorded off, so Settings › Network lists it to allow.
3. It sends `POST <server>/api/v1/license/refresh` with `{"key": "<key>"}` and `User-Agent: SurfSense`, as update checks name themselves: the key in the body, never in the URL, and no device or install identifier, since the app has none. The timeout is ten seconds, and a redirect is not followed.
4. A 200 answers the file, a lapsed license's included; any other answer is a code below.
5. It reads the stored license again, since the fetch took time. If the user removed or replaced it meanwhile, nothing is imported and the route answers the current status. A file for another key is refused as `refresh_unavailable`, because rule 7 matches on the key. Otherwise the file goes through `import_certificate()`, as `PUT /license` does, and takes the stored file's place; a file it refuses keeps that rejection's code, with 422.

| Code | Status | When |
|---|---|---|
| `license_none` | 409 | no license is stored |
| `refresh_egress_blocked` | 403 | the license server's host is not allowed in Settings › Network |
| `refresh_not_found` | 404 | the server has no license with that key |
| `refresh_refused` | 403 | the license is not in good standing, as when suspended or banned; shown, and it never disables the app |
| `refresh_rate_limited` | 429 | the server's limit, 30 refreshes an hour per key and 60 per address |
| `refresh_unavailable` | 503 | the server is out of reach or too slow, answered 503 because Keygen is, answered anything else unexpected, or sent another license's file |

Each failure answers `{code, message}`, like `PUT /license`, with the messages in `router.py`, and leaves the stored file as it was.

### The daily check

`renewing_daily()` in [`renewal/renewal_schedule.py`](../../../surfsense_local/backend/modules/license/renewal/renewal_schedule.py) runs for the API's lifespan: one check at startup, then one every 24 hours (`CHECK_EVERY`) whatever the outcome, so a server that is down is asked again the next day, never in a loop. A check, `renew_if_due()` in `renewal/automatic_renewal.py`, sends something only when all of these hold:

- a license is stored;
- its plan is `business`: a trial, the Business one included, is extended only by hand, so it is left to Settings' button;
- its expiry is at most 30 days away (`RENEW_WITHIN`) and at most 30 days past (`GIVE_UP_AFTER`). The license ends 30 days after the period paid for, so the checks start when that period ends, and stop once only support could still extend it, which leaves a month for an invoice paid late;
- the license server's host is allowed.

It raises no dialog, since nothing the user did started it: a host not allowed is logged as `refresh_egress_blocked` and nothing is sent ([ADR 0060](../../adr/0060-one-consent-question-per-user-action.md)). That is as far as an air-gapped install's check ever gets, and a new install's, until the user allows the host through Check for renewal's question or in Settings › Network. Its other failures are logged and wait for the next day. A file it imports shows in Settings at the next status read.

## Settings and the sidebar

Settings › License adds a license by choosing a `.lic` file or pasting its text, which the renderer sends to `PUT /license`. It shows:

- the plan, from `planName()` in `plan-name.ts`: the plan's own word, capitalised, and a `business` license for one person as Solo;
- "Licensed to" the firm, when the file names one;
- the email;
- "Expires" or "Ended" with the date, beside a team's seats or a Business license's people, Solo's one person included;
- "Jobs:" with each job's name from `job-names.ts`, a code this version cannot name shown as sent;
- Replace and Remove buttons.

A Business license, or a trial carrying jobs, adds a Renewal row (`license-renewal.tsx`). Its Check for renewal calls `POST /license/refresh`, asking about the license server first when it is off ([renewal](#renewal)), and answers "Renewed until" the new date when the expiry moved later, "No renewal yet" when it did not, or the failure's message. Replace and Remove wait while a check runs, and replacing or removing clears the last check's answer.

A notice shows when the clock is off, when the license has expired, and when it runs out within 14 days. With no license stored, both Start a free trial and the pricing link open `/pricing`. The expired notice links to `/pricing` too: for a Business license or a trial carrying jobs it says Check for renewal fetches the new file if the license was renewed, and for any other plan that a renewal comes as a new file to add here. Every link goes through the About section's `ExternalLink` to the OS browser. The [portal](portal.md) has no accounts ([ADR 0024](../../adr/0024-portal-without-accounts.md)), so no string in the app sends the user to one. The links are an offer, never a wall. The sidebar footer carries one status row: green for `active`, red for every state that leaves plugins locked.

## The compiled key

The release workflow's step "Refuse to build with the test signing key" runs `tests/packaging/test_license_key.py` before it freezes anything. The test fails when the fixture key in [`docs/contracts/license-sample/public-key.hex`](../../contracts/license-sample/public-key.hex) is among the compiled keys: the fixture files are signed from a seed that is public in the repo, so shipping that key would let anyone sign a license. `pyproject.toml` excludes the `packaging` marker by default, and the step's own `-m packaging` wins ([packaging](../packaging.md)). The test proves only that the fixture key is absent.

## Known gaps

None.
