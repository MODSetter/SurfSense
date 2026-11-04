# Contract 6: job pack delivery

How a SurfSense license gets its job plugins: the desktop app asks the license server for the newest job pack its license may run, and the server answers with that pack's signed zip, from its own host. Version 1 (3 Nov 2026). Why it works this way is [ADR 0082](../adr/0082-the-license-server-delivers-job-packs-from-private-releases.md); why a job is a paid plugin is [ADR 0067](../adr/0067-b2b-jobs-ship-as-paid-plugins.md); which license unlocks it is ADR 0080 (one Business license, priced per person; on the `docs/business-license` branch).

| Side | Who | Built |
|---|---|---|
| Producer | The license server's `POST /api/v1/license/job-pack` ([portal](../architecture/license/portal.md#post-licensejob-pack)), in `backend/license/job_packs/` | Yes |
| Producer | The pack publisher, `tools/publish_pack.py` in the private pack repository, whose GitHub releases the server reads | Yes, outside this repository |
| Consumer | The desktop app's pack delivery and hand import, in `surfsense_local/backend/modules/jobs/packs/delivery/` | No: it comes with the app's Jobs screen |

## Format

### Request

```
POST /api/v1/license/job-pack
Content-Type: application/json
User-Agent: SurfSense

{"key": "<data.attributes.key>", "entitlement": "JOB_QUESTIONNAIRE", "installed_version": "0.4.3", "runners": ["workbook-rows/1"]}
```

| Field | Type | Meaning |
|---|---|---|
| `key` | string, 1 to 1,024 characters once trimmed | The license key, `data.attributes.key` from the license file ([contract 1](01-license-file.md)). In the body, never in the URL. |
| `entitlement` | string matching `^[A-Z][A-Z0-9_]{0,63}$` | One job code from the license's `metadata.jobs`, such as `JOB_QUESTIONNAIRE`. One code per request; consumer rule 1 says which. |
| `installed_version` | `x.y.z`, each part 1 to 9 ASCII digits; or absent, or `null` | The highest version installed of a pack that has a job for `entitlement`; absent when none is installed. |
| `runners` | 1 to 16 strings matching `^[a-z][a-z0-9-]{0,63}/[1-9][0-9]{0,5}$` | Every job runner the app ships, such as `workbook-rows/1`. |

The server ignores a field it does not know, so a later app may add an optional one in this version.

### Answers

| Status | `detail.code` | When |
|---|---|---|
| `200` | | The newest pack this license and app may get, newer than `installed_version` or with nothing installed: the zip below |
| `204` | | `installed_version` is that pack's version, or newer |
| `403` | `license_not_valid` | Keygen validates the license as anything but `VALID`; the message names Keygen's code, such as `EXPIRED` or `SUSPENDED` |
| `403` | `job_not_included` | The license's `metadata.jobs` does not list `entitlement` |
| `403` | `pack_not_covered` | Every pack with a job for `entitlement` also has a job whose entitlement the license's jobs do not list |
| `404` | `license_not_found` | No license has the key |
| `409` | `needs_newer_app` | The packs this license may get have a job for `entitlement`, but each names a runner outside `runners` |
| `422` | `unknown_job` | `entitlement` is not a job SurfSense sells |
| `429` | `rate_limited` | The caller's address, or the key, has asked too often this hour |
| `503` | `job_packs_unavailable` | Keygen or the pack store cannot be read, or no pack with a job for `entitlement` is published |

A refusal's body is `{"detail": {"code": "<code>", "message": "<a sentence a person can read>"}}`. A body that breaks the request's rules gets `422` whose `detail` is a list of `{type, loc, msg}`; it never echoes the request, and it is always the caller's bug.

The server checks in this order and answers at the first check that fails: the request's rules, the rate limit, `entitlement` among the jobs SurfSense sells, the license's validation, the license's jobs, the pack store, the license's jobs against every job of the packs, the runners.

| Header | On | Value |
|---|---|---|
| `Content-Type` | `200` | `application/zip` |
| `Content-Disposition` | `200` | `attachment; filename="<id>-<version>.zip"` |
| `X-Job-Pack-Id` | `200`, `204` | the pack's `id` |
| `X-Job-Pack-Version` | `200`, `204` | the version sent, or for `204` the newest this license and app may get |
| `Cache-Control` | `200`, `204` | `no-store` |

### The zip

What a `200` carries, and the only shape a published pack has. A person may import the same zip by hand. Each rule holds on every system, whatever its file system would accept.

A file imported by hand may also wrap the pack, as zipping its folder does: when every file in the zip sits in one top folder that holds `job-pack.json`, the app reads the pack inside that folder. The server never serves such a zip.

- **Members.** `job-pack.json` and `job-pack.sig` at the root, and each file `job-pack.json` lists, at its listed path. Nothing else: no folder wrapping the pack, no file the manifest does not list. Each member is a plain file, stored or deflated, not encrypted; a directory entry may also appear, counts as a member and carries nothing (its declared size is 0).
- **Names.** Relative POSIX paths in normal form: no `\`, no `:`, no leading `/`, no empty, `.` or `..` part (a lone `.` among them), no part ending in a dot or a space, no part Windows reserves (`CON`, `PRN`, `AUX`, `NUL`, `COM1` to `COM9`, `LPT1` to `LPT9`, in any case, with or without an extension), none of `<`, `>`, `"`, `|`, `?` and `*`, and no character below U+0020. A name is at most 255 bytes in UTF-8, a directory entry's final `/` aside: no disk holds a longer part, and no pack needs a longer name. No part ends in `~` and ASCII digits before its last dot, or at its end when it has no dot, as a Windows short name such as `REPORT~1.MD` does: Windows opens the file a short name stands for, so such a member could be written over another file. No two names are equal when compared without case, no name is also the folder of another member (a file `a` beside `a/b`, or beside a directory entry `a/`), and a folder is spelled one way: no two folder names are equal when compared without case.
- **Size.** The zip, and the sum of its members' sizes once extracted, are each at most 52,428,800 bytes (50 MiB), in at most 1,000 members, directory entries included.
- **`job-pack.json`**, UTF-8 JSON with no byte-order mark, is one object:

| Field | Meaning |
|---|---|
| `schema` | `surfsense-job-pack/1` |
| `id` | `^[a-z][a-z0-9-]{0,63}$`, the same in every version of the pack |
| `version` | `x.y.z`, each part 1 to 9 ASCII digits, compared as three integers, left to right |
| `name`, `publisher`, `description` | non-empty strings |
| `access` | `paid` for every pack this route serves |
| `license_file` | a listed file: the pack's license terms |
| `jobs` | one or more objects, each with a `key` unique in the pack (`^[a-z][a-z0-9-]{0,63}$`), `name`, `description`, `runner` (a name and a version matching the pattern of the request's `runners`, such as `workbook-rows/1`), `config` (a listed file), optionally `skill` (a folder named `surfsense-job-...` whose `SKILL.md` is listed), and `entitlement` (`^[A-Z][A-Z0-9_]{0,63}$`, the license code that unlocks the job), which every job of a `paid` pack has |
| `files` | every file in the pack but these two, by path, to its sha256 in 64 lowercase hex digits |

Both sides read `id`, `version`, `name`, `publisher`, `description` and `license_file`, and a job's `key`, `name`, `description`, `runner` and `config`, with white space at their ends trimmed, and hold what is left to the patterns above. Other fields are signed and ignored.

- **`job-pack.sig`** holds one to eight lines, each the standard base64 of a 64-byte Ed25519 signature; blank lines and a final newline are ignored. Each signs the bytes `surfsense-job-pack/1\n` followed by the manifest in canonical JSON: the value `job-pack.json` parses to, written with sorted keys, `,` and `:` as separators and no ASCII escaping, in UTF-8 (in Python, `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")`). The keys are SurfSense's pack public keys: raw 32-byte Ed25519 keys in hex, newest first, compiled into both sides (`PACK_PUBLIC_KEYS_HEX`), never read from configuration. An app accepts a pack when any line verifies with one of its keys; the server serves it only when every line verifies with one of its keys. A pack signed with an old key and a new one installs on apps that trust either.

A pack is its `id` and `version`; once published, that pair never names other bytes.

## Producer rules (`backend/license/job_packs/`, and the publisher)

1. The route is served with the license portal, only when `KEYGEN_API_TOKEN` is set.
2. **The key** travels in the body. Neither the key nor the body is logged, and no answer echoes them. The rate limit names its key bucket by the first 32 hex digits of the key's sha256. The server keeps nothing about a request beyond those counts, dropped an hour after the caller's last request, and its access log's line for it, kept as its other logs are. Keygen records when the license was last validated.
3. **The license.** Keygen's `validate-key`, unscoped, as the product token, must answer `VALID`. `EXPIRED` gets nothing, because a Business license's expiry is already the end of the year paid for plus 30 days ([contract 1](01-license-file.md), producer rule 7) and a trial ends at its expiry. The refresh still serves an expired license its file; this route does not.
4. **The job.** The license's `metadata.jobs`, read as the app reads it (split on commas, each code trimmed, empty and repeated codes dropped; anything but a string lists none), must list `entitlement`. Keygen's policy entitlements are not read, so the server never delivers a pack the app would keep locked.
5. **The pack.** Of the packs with a job for `entitlement`, the server keeps those whose every job's `entitlement` the license's jobs list, then those whose every job's `runner` is in `runners`, since an app refuses a whole pack that names a runner it lacks, and picks the highest `version`. It answers `503` when no pack has a job for `entitlement`, `403` `pack_not_covered` when none passes the first filter, `409` when none passes the second, and `204` when `installed_version` is the chosen version or higher. A pack that needs something an older app lacks, a new runner or a later `schema`, names a runner only the apps that have it list.
6. **Checked before it is served.** The server serves a zip only after checking it against the zip section, with the same pack public keys the newest app compiles in, and after checking that `access` is `paid`, that every job has an `entitlement`, and that `id` and `version` match the release's tag and asset name. A zip that fails, or that cannot be read at all, is never served and is logged with its reason; versions that passed keep being served.
7. **The bytes come from the route,** out of the server's memory. The server never redirects, so the app reaches no host but the license server.
8. **The store.** Packs are GitHub releases of one private repository that holds only releases: a release tagged `<id>-v<version>` with one asset, `<id>-<version>.zip`. Drafts and prereleases are not served. A folder of zips named `<id>-<version>.zip` may stand in for it. The server reads the store at most every `JOB_PACKS_CACHE_SECONDS` (600 by default), downloads each release once, and keeps the last good packs while the store fails, so a new version reaches apps within that time.
9. **Versions only grow, under one id.** A published release's asset is never replaced; a fix is a new, higher version. Once a pack with a job for an entitlement is published, every later pack with a job for it has the same `id` and a higher `version`.
10. No analytics event is sent for a delivery.

## Consumer rules (`surfsense_local`)

1. **When.** One request per code in the license's `metadata.jobs` that matches the `entitlement` pattern, only while the license is `active`, a trial included: on the user's action (adding or replacing a license, Check for renewal, Download, Check for updates), at startup, once a day, and once a run that held a check back ends (rule 5). Any other code is reported as `unknown_job` without a request.
2. **Consent.** Before connecting, the app checks the license server's host, `host:api.surfsense.com` unless a developer or a mirror sets another, with purpose `job_packs`. A user's action asks; background work never asks, and logs the refusal and stops ([ADR 0017](../adr/0017-egress-off-by-default.md), [ADR 0060](../adr/0060-one-consent-question-per-user-action.md)).
3. **The request.** `POST <license server>/api/v1/license/job-pack` with the body above and `User-Agent: SurfSense`; `runners` is exactly the runners the app ships. The key goes nowhere else for a pack, and the app never asks Keygen or GitHub. It follows no redirect, so a `3xx` is a failure, and allows 10 s to connect and 60 s per read.
4. **The body.** On `200` the app requires `Content-Type: application/zip` (parameters ignored), streams the body to a temporary file, and stops past 52,428,800 bytes. The headers are hints for logs and the screen; the zip's own manifest decides.
5. **Install.** The app installs the zip only when it passes the app's own checks of the zip section (names, manifest, signature, files), its manifest has a job for the requested `entitlement`, every job's `entitlement` is in the license's jobs, and its version is newer than the installed pack with a job for that entitlement. A file the user imports by hand may also be the same version, when it is the same signed pack. It never replaces a pack while a run of it is pending or processing, checking again once the run ends, installs one pack at a time, and keeps the installed version until the new one is in place. Anything that fails leaves the installed pack as it was. A download refused because it holds a job the license's file does not list says the license has changed and to check for renewal.
6. **Answers.**

| Answer | The app |
|---|---|
| `200` `application/zip` | installs as in rule 5 |
| `200` of another type | keeps the installed pack and tries again at the next check |
| `204` | changes nothing: the installed pack is current |
| `403` `job_not_included` | keeps any installed pack and says the license does not include the job |
| `403` `pack_not_covered` | keeps any installed pack and says the job comes only in a pack with a job the license does not include |
| `403` with another code | keeps any installed pack and says the license server did not accept the license |
| `404` `license_not_found` | keeps any installed pack and says no license has the key |
| `409` `needs_newer_app` | keeps the installed pack and says the job needs a newer SurfSense |
| `422` `unknown_job` | keeps the installed pack and logs it |
| `422` whose `detail` is a list | keeps the installed pack and logs only the status and each error's `type` and `loc`: it is the app's own bug |
| `404` or `405` whose `detail` is not an object (a server without this route), `429`, `503`, any other status, no answer, a timeout, a body too large | keeps the installed pack and tries again at the next check or user action, never in a loop |

7. A refused or failed request never removes or changes an installed pack, and the app never logs the key.

## Fixture

`job-pack-sample/` is written by `generate.py`, which needs the standard library and `cryptography`, from a fixed seed, so re-running it is byte-identical:

| File | What it is |
|---|---|
| `sample-jobs-1.0.0.zip` | a made-up paid pack, `sample-jobs` 1.0.0, with one job, `sample-questionnaire` (runner `workbook-rows/1`, entitlement `JOB_QUESTIONNAIRE`), and two listed files, `LICENSE.txt` and `jobs/sample-questionnaire/job.json`; stored, manifest and signature first, one signature line |
| `public-key.hex` | the raw 32-byte Ed25519 public key that signed it, in hex |
| `generate.py` | writes both, then checks the sample's own shape (stored, manifest and signature first, one signature line that verifies, the listed files and no others, each with its sha256), that a changed byte in a listed file fails its sha256, and that a changed manifest fails the signature; the server's tests check the sample against the whole zip section |

It is signed by a **test** key that no release trusts, and holds no real pack's content.

## Tests each side owns

- Server ([`backend/license/tests/`](../../backend/license/tests/)): the sample passes the server's checks with its key trusted and is served byte for byte from a folder store; the compiled pack keys leave out the sample's and the tests' keys; each refusal in the zip section, an unreadable zip among them; each answer and code in the order above, `EXPIRED` refused, a pack holding a job the license lacks withheld with `pack_not_covered`; the runner filter and `204`; both rate-limit buckets, the address first and the key out of their names; a malformed body's `422` echoes nothing; the GitHub store's listing, one download per release, its redirect followed without the token, and the last good packs kept while it fails or a release is broken or too slow to check.
- App: the sample installs with its key trusted and is refused with the shipped keys alone, in a test that skips only while the repository it runs in lacks this contract; a file imported by hand that wraps the pack in one folder installs; each refusal in the zip section, the differences by design below aside, its lists of manifest cases and listed-name cases the same as the server's; a code outside the `entitlement` pattern never sent; the user's action asking to reach the license server, a download a run holds back included, and background work never asking; each answer leads to consumer rule 6's outcome; no redirect followed; a `200` that is not a zip not installed; a body past the cap stopped; no pack replaced during a run of it, and the check made again once the run ends; a download holding a job the license's file lacks asking for a check for renewal; the installed pack kept when anything fails.
- Publisher: `tools/publish_pack.py --dry-run` passes a pack through the app's checks and the server's before any release is made.

Each side has its own cases for the zip section: the server's tests run in CI on Linux, the app's on Linux, macOS and Windows. By design, these are the only zips one side takes and the other refuses:

- a wrapped pack: the app installs one imported by hand, and the server refuses it;
- a `job-pack.sig` with a line no trusted key made beside one that verifies: the app installs it, and the server, which needs every line to verify, refuses it;
- a pack that is not `paid`, has a job with no `entitlement`, or is published under a tag or asset name other than its `id` and `version`: the server never serves it (producer rule 6), and the app installs it, running a free pack's jobs and keeping a paid pack's job with no `entitlement` locked;
- a pack naming a runner the app lacks: the server serves it only to an app whose `runners` lists that runner (producer rule 5), and the app refuses it with `NEEDS_NEWER_APP`.
