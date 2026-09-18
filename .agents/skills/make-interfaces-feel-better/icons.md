# Icons

Icon weight, states, sizing, and direction: the details that make icons sit naturally in an interface.

## Match Icon Stroke to Text Weight

An icon next to text should carry the same optical weight as the text.

| Adjacent text | Icon stroke width (24px grid) |
| --- | --- |
| Regular (400), 14–16px | `1.5px` |
| Medium/Semibold (500–600) | `2px` |
| Bold (700), or emphasized standalone | `2.5px` |

Use one stroke weight per icon set on a surface. Size inline icons relative to the text's cap height, typically `1em`–`1.25em`.

## One SVG, Recolored per State

Use one SVG drawn with `currentColor`; let CSS drive hover, selected, and disabled states. Strip hardcoded `fill` and `stroke` colors when importing icons.

```html
<svg fill="none" stroke="currentColor" stroke-width="2">…</svg>
```

```css
.icon-button { color: oklch(0.552 0.016 285.938); }
.icon-button:hover { color: oklch(0.21 0.006 285.885); }
.icon-button[aria-pressed="true"] { color: oklch(0.623 0.188 259.815); }
.icon-button:disabled { opacity: 0.4; }
```

## Outline Default, Fill Active

| Variant | Use for |
| --- | --- |
| Outline | Default state: toolbars, list rows, inline with text |
| Fill | Selected or active state: active tab, toggled bookmark, liked heart |

The swap between variants is a contextual icon animation; use the exact cross-fade values in [animations.md](animations.md).

## Design at Render Size

- Test every icon at the smallest size it will render, often `16px`.
- Prefer simplified glyphs for small contexts over scaled-down detailed artwork.
- Use the icon set's native grid sizes (`16`, `20`, `24`) rather than arbitrary fractional scales.
- Use SVG rather than raster assets.

## Icons in RTL

| Flip | Don't flip |
| --- | --- |
| Back/forward arrows, navigation chevrons | Logos and brand marks |
| Text alignment, lists, indent | Checkmarks |
| Directional send glyphs | Clocks, cups, pencils |
| Speaker waves tied to reading direction | Media playback controls |

```css
[dir="rtl"] .icon-directional {
  scale: -1 1;
}
```

Analyze composite icons part by part: an overlay may keep its position even when the base glyph flips. Give every icon-only control an accessible name and mark purely decorative icons hidden from assistive technology.
