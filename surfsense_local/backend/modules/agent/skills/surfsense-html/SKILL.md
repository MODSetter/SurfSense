---
name: surfsense-html
description: Make or change a web page from the user's sources - a report, a briefing, a dashboard, a comparison, a timeline, an explainer, an interactive calculator or a figure that shows how something works - by writing an HTML file and keeping it with surfsense_save_page. Load it whenever the user asks for a web page, an HTML page, an interactive page, or a change to one you made.
---

# Web pages

You write the page yourself, as one HTML file under `outputs/`, and keep it with `surfsense_save_page`. SurfSense stores it as a version in Studio, where the user opens it, and shows you screenshots of it. To change it later you edit the same file and save again, which makes the next version.

Before you write, read `design.md` in this skill's folder: how a page should look and move. Read `figures.md` and `kit.md` only when the page needs a figure of a mechanism.

## The contract

- One complete HTML document: `<!doctype html>`, `<html lang>`, `<head>` with `<meta charset="utf-8">`, `<meta name="viewport" content="width=device-width, initial-scale=1">` and a `<title>`, then `<body>`.
- Everything inline: CSS in `<style>`, code in `<script>`, images as `data:` URLs or inline SVG.
- **The page has no network.** The viewer blocks every request: no CDN, no web font, no `fetch`, no image from a URL, no form that submits. Use system fonts, draw charts as SVG, and write the data into the page. A save lists anything the page asks to load, so you can take it out.
- No `eval` or `new Function`; they are blocked too.
- At most 5 MB, the figure kit included. A page is usually 10 to 80 KB.
- Write it at `outputs/<short-name>.html` with your own file tools. It stays there for the next edit.
- Only what the sources and the user support. Every figure, date and name on the page is one you found or were given.

## Saving

Call `surfsense_save_page` with `path` (such as `outputs/q3-report.html`) and `title` (as Studio lists it). It waits until the page is ready, then returns:

- `Rendered artifact <id>, version <n>: <title>` and the page's opening text, as search will read it;
- the outside resources the viewer will block, if the page names any;
- up to four screenshots: the page at 1,280 px wide, top to bottom, 1,000 px each, with reduced motion on.

Look at every screenshot before you answer. Fix what is wrong: text that overflows or overlaps, a chart that did not draw, colours that do not read, an empty area where something should be. Then save again with `artifact_id`. When a page needs script to show anything at all, check the screenshot shows it: a page that is blank until it animates is broken under reduced motion.

## Editing a page you made

- Edit the working file the save named, changing only what the user asked, then save it with `artifact_id`. Make every change asked for in that save, and say what you assumed.
- Keep the same `path` and `title`. A save without `artifact_id` under a title this chat already used is refused, naming the id to pass.
- If the working file is gone, write the page again in full and save it with `artifact_id`.
- A page Studio made cannot take a version here: save a new page instead.

## When a save is refused or fails

A refusal names the fix: a path outside `outputs/`, a file that is not `.html`, too large, not UTF-8, no HTML in it, an unknown kit. Fix it and save again. If this is your third failed save for this request, stop and tell the user what failed.

## Example

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Q3 revenue</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #fbfaf7; --surface: #ffffff; --text: #1d1d1b; --muted: #6b6a65;
    --border: #e4e2dc; --accent: #2f6f5e; --bar: #2f6f5e; --bar-muted: #c9d8d2;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #161614; --surface: #1f1f1d; --text: #ecebe6; --muted: #a3a29b;
      --border: #34332f; --accent: #7cc4ad; --bar: #7cc4ad; --bar-muted: #34463f;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
    font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 68ch; margin: 0 auto; padding: 48px 20px 64px; }
  h1 { font-size: clamp(1.9rem, 5vw, 2.6rem); line-height: 1.15; margin: 0 0 8px; }
  .lede { color: var(--muted); margin: 0 0 32px; }
  .figures { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 0 0 40px; }
  .figure { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
  .figure b { display: block; font-size: 1.9rem; line-height: 1.1; font-variant-numeric: tabular-nums; }
  .figure span { color: var(--muted); font-size: .9rem; }
  svg { width: 100%; height: auto; display: block; }
  .bar { fill: var(--bar-muted); }
  .bar.lead { fill: var(--bar); }
  .label { fill: var(--muted); font-size: 13px; }
  .value { fill: var(--text); font-size: 13px; font-variant-numeric: tabular-nums; }
  @media (prefers-reduced-motion: no-preference) {
    .bar { transform-box: fill-box; transform-origin: left; animation: grow .6s cubic-bezier(.2,.7,.2,1) both; }
    @keyframes grow { from { transform: scaleX(0); } }
  }
</style>
</head>
<body>
<main>
  <h1>EMEA led Q3 growth</h1>
  <p class="lede">Revenue rose 12% to 4.2 million, from the Q3 board pack.</p>
  <section class="figures" aria-label="Key figures">
    <div class="figure"><b>4.2M</b><span>Q3 revenue</span></div>
    <div class="figure"><b>+12%</b><span>on Q2</span></div>
  </section>
  <h2>Revenue by region</h2>
  <svg viewBox="0 0 600 130" role="img" aria-label="Revenue by region: EMEA 1.9 million, Americas 1.5 million, APAC 0.8 million">
    <text class="label" x="0" y="24">EMEA</text><rect class="bar lead" x="90" y="8" width="420" height="24" rx="3"/><text class="value" x="518" y="24">1.9M</text>
    <text class="label" x="0" y="66">Americas</text><rect class="bar" x="90" y="50" width="332" height="24" rx="3"/><text class="value" x="430" y="66">1.5M</text>
    <text class="label" x="0" y="108">APAC</text><rect class="bar" x="90" y="92" width="177" height="24" rx="3"/><text class="value" x="275" y="108">0.8M</text>
  </svg>
</main>
</body>
</html>
```
