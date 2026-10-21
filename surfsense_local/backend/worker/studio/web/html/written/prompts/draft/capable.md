Write one complete web page, a single HTML file, from the sources below. The reader opens it cold and will never see the sources.
$focus
How to work the material:

- The sources are raw material, not an outline to walk. Decide what the page is for, lead with what the sources add up to, and let its structure follow: a report, a comparison, a timeline, a set of key figures, a guide. A section per source is the failure mode.
- Prefer the specific figure, date or name over the general statement. Where sources disagree, say so and give both. Say when something is proposed, pending or a draft.
- Put only facts the sources state on the page: no outside knowledge, no invented precision, never a placeholder. A chart shows only numbers the sources state.
- You tend to converge on generic, on-distribution pages. Resist it: the page should be one only this material could support.

The contract:

- One complete document, from `<!doctype html>` to `</html>`, with `<html lang>`, `<meta charset="utf-8">`, a viewport meta and a `<title>` naming the page.
- Everything inline: CSS in `<style>`, any script in `<script>`, images as inline SVG or `data:` URLs.
- The page has no network: no CDN, no web font, no image from a URL, no `fetch`, no form that submits. Use system fonts and draw charts as SVG with the data written in.
- No `eval` and no `new Function`.
- At most $limit. The page must end in this one reply: keep it to what the material needs.

How the page looks and moves:

$design

Return only the HTML, from <!doctype html> to </html>. No prose before it, no explanation after it.
