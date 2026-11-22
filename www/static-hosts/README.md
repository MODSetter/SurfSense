# Static hosts

A small static Vercel project, separate from the website, that answers for two hostnames
after the Coolify VM (4.242.19.145) shuts down with SurfSense Inc. on 27 November 2026:

| Host | Serves | For |
|---|---|---|
| `plugins.surfsense.com` | `/plugins.json`, `/plugins.json.sig`, `/icons/*`, `/oauth/client.json`, `/oauth/callback`, `/health` | Every installed 2.x app: the third-party plugin list, its icons, and OAuth plugin sign-in |
| `api.surfsense.com` | `/health` only, as `{"sunset": true, "sunset_url": "https://www.surfsense.com/sunset"}` | Legacy 0.0.x desktop apps, which check it at startup and then open the "get the new app" page |

Anything else is a 404, including the paid scraper plugins (`/<name>/mcp`), which were live
servers and are gone.

It is its own project, rather than host rewrites in `www`, so no website page can ever answer
on these hosts and the files are served exactly as committed, with no Next.js in between.

## The files

`public/` mirrors what the registry container (`backend/plugins/registry/`, see its
`Caddyfile`) served, byte for byte: the same paths and the same headers, set in
`vercel.json`. `static-hosts.test.ts` (part of `pnpm test:unit` in `www`) checks that:

- each served file equals the committed registry file;
- `oauth/client.json` still has the exact sha256 installed apps sign in with. Never edit it:
  its URL is the OAuth client id every installed 2.x app uses;
- each path gets the Caddyfile's headers, the callback with `no-store` and
  `frame-ancestors 'none'`;
- `api.surfsense.com/health` returns the sunset JSON.

`.gitattributes` marks `public/` as `-text`, so no checkout converts line endings.

When the registry's signed list changes (a new third-party plugin merged on dev), the test
fails until the copies are refreshed. From the repository root:

```bash
for f in published/plugins.json published/plugins.json.sig; do
  git show HEAD:backend/plugins/registry/$f > www/static-hosts/public/${f#published/}
done
```

Copy changed icons the same way, with `git show`, never a file copy from a Windows checkout.

## Vercel setup (once)

1. In Vercel, **Add New › Project**, import `MODSetter/SurfSense` again.
2. **Root Directory:** `www/static-hosts`. **Framework Preset:** Other. Leave the build,
   output and install commands empty; `vercel.json` sets the output directory to `public`.
3. Production branch: `main`, like the website.
4. **Settings › Git › Ignored Build Step:** "Only build if there are changes in a folder",
   `www/static-hosts`, so a website change doesn't redeploy it.
5. Deploy, then check the `*.vercel.app` address: `/plugins.json`, `/oauth/client.json`
   and `/oauth/callback` answer, and `/health` is a 404 there (it answers only on the two
   hostnames).
6. **Settings › Domains:** add `plugins.surfsense.com` and `api.surfsense.com`. Vercel
   shows the DNS record each needs; change the records in GoDaddy as it says (see the
   launch-day checklist).
