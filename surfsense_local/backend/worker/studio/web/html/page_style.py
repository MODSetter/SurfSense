"""The simple page's stylesheet: the agent's pages' paper palette and type, fixed.

The skill's examples (modules/agent/skills/surfsense-html/examples/) set these
colours; light only, as design.md has every page. A module, not a .css file:
the frozen worker bundles only Studio's .md files.
"""

PAGE_STYLE = """
:root {
  color-scheme: light;
  --bg: #f4f1ea; --surface: #fffdf9; --text: #1d1c19; --muted: #5a564c;
  --border: #e0d9cb; --accent: #0f6874;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 17px/1.6 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  overflow-wrap: anywhere;
}
main { max-width: 760px; margin: 0 auto; padding: 56px 24px 72px; }
h1 {
  font: 700 clamp(1.9rem, 5vw, 2.6rem)/1.15 "Iowan Old Style", "Palatino Linotype", Georgia, serif;
  margin: 0 0 32px; padding-bottom: 20px; border-bottom: 2px solid var(--accent);
}
.summary { font-size: 1.15rem; color: var(--muted); max-width: 60ch; margin: -12px 0 8px; }
section { margin-top: 40px; }
h2 { font-size: 1.3rem; line-height: 1.25; margin: 0 0 12px; color: var(--accent); }
p { max-width: 64ch; margin: 0 0 14px; }
ul { max-width: 64ch; margin: 0 0 14px; padding-left: 1.3em; }
li { margin-bottom: 6px; }
li::marker { color: var(--accent); }
"""
