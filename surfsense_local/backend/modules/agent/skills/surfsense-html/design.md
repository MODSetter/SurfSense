# How a page looks and moves

A page made from the user's sources is read by someone who never saw them. It should look made for this material: a reader should be able to tell what it is about from across the room. Plain black text on white, a centred column of identical cards, or a gradient hero with three icons is the generic page; avoid it.

## Start from the material

- Decide what the reader most needs, and put it first and largest: the finding, the number, the decision, the date.
- Pick one structure the content earns: a report reads top to bottom; a comparison is side by side; a timeline runs along time; a dashboard groups figures by what they measure; a guide is numbered steps.
- Every figure, date and name comes from the sources. A chart shows only numbers the sources state.

## Layout

- Mobile first. The page works from 360 px wide to a wide desktop with no horizontal scroll: `max-width: 100%` on images, SVG and tables in a scrolling wrapper, `minmax(0, 1fr)` grid columns, and `overflow-wrap: anywhere` on long words and URLs.
- Body text at a readable measure, 60 to 75 characters (`max-width: 68ch`). Wide things, tables, charts and figures, may run wider than the text.
- Use CSS grid for layout and `gap` for spacing. Space on a scale (4, 8, 12, 16, 24, 32, 48, 64 px), more between sections than within them.
- Group with space and alignment before borders and boxes. A card is for a thing the reader compares with its neighbours, not for every paragraph.

## Type

- System font stacks only; the page cannot load a web font. Text: `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`. Serif for a long read: `"Iowan Old Style", "Palatino Linotype", Georgia, serif`. Figures and code: `ui-monospace, "SF Mono", Menlo, Consolas, monospace`.
- One type scale, about 1.25 apart (for example 14, 16, 20, 25, 31, 39 px), with `clamp()` on the largest so a heading fits a phone.
- Body 16 to 18 px, line height 1.5 to 1.65; headings tighter, 1.1 to 1.25.
- Numbers that line up use `font-variant-numeric: tabular-nums`.
- One `h1`, then `h2` and `h3` in order. Never skip a level for size; style the level instead.

## Colour

- **Light only.** A page is a document, as a Word file or a PDF in Studio is: a light background with dark text. Set `color-scheme: light` and give `body` its background. Write no `prefers-color-scheme: dark` scheme.
- **The palette is yours.** Choose colours that suit the material; nothing here fixes them.
- **Contrast against what each thing sits on.** Text at least 4.5:1 against its own background, large text, chart marks and control borders at least 3:1. That holds for muted text, for text on a tinted surface, for the accent used as text, and for text on an accent fill. No pale grey or pastel text for content.
- Define colours once as custom properties on `:root`, and use only those: a background, a raised surface, text, muted text, a border, one accent, and the few colours a chart's series need.
- One accent, used for what to look at first. Colour never carries meaning alone: label the series, mark the change with a sign or a word as well.

## Controls and access

- Native elements: `button`, `input`, `select`, `details`. Every input has a `label`. A custom control gets its role, its name and the keys it answers.
- A visible focus ring on everything focusable: `:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`.
- Touch targets at least 44 px.
- Images and figures get `alt`, or `role="img"` with an `aria-label` on an SVG, that says what they show, not what they are.

## Charts

Draw them as inline SVG with a `viewBox`, so they scale. No chart library: the page cannot load one.

- Choose by the question: a bar for comparing amounts, a line for change over time, a single big number with its change for one figure. Avoid pie charts beyond three parts.
- Bars start at zero. Label axes in the data's units, and label values directly where it is clearer than a legend.
- Light grid lines or none. The data in the strongest colour, everything else muted.
- Give a chart a title that says what it shows ("EMEA grew fastest"), and its numbers in a `table` or the text as well, for screen readers and search.

## Motion

Motion explains or it goes. A chart's bars growing to their values, a number counting up to its total, a step lighting as the reader reaches it, a part moving the way the real thing does: these carry meaning. Animating every card on scroll does not.

Draw with SVG and CSS only. No WebGL, no 3D canvas and no shader: they make a page heavy and laggy, and an SVG figure or chart says the same thing.

- **Time-based.** Move by elapsed time from `requestAnimationFrame` timestamps, with each step's `dt` clamped to 1/30 s so a background tab does not jump. Never move a fixed amount per frame.
- **Ease toward a target.** Input sets a target; the value follows, `x += (target - x) * (1 - Math.exp(-dt / tau))` with `tau` 0.1 to 0.3 s, or a spring where the subject is springy. Nothing snaps to the pointer.
- **One loop, and it stops.** One `tick(dt)` updates the state and writes the DOM directly (`setAttribute`, `textContent`, `style.transform`). Stop the loop once everything has reached its target, and while the element is off screen: an `IntersectionObserver` with `rootMargin: "120px 0px"`, reading the newest entry.
- **Reduced motion.** Under `prefers-reduced-motion: reduce`, show the end state at once: no tour, no flow, no pulse. The page must still answer input and still make sense; this is how SurfSense takes its screenshots.
- **CSS for the simple cases.** A transition or a keyframe animation is enough for a hover or a one-off reveal. Wrap it in `@media (prefers-reduced-motion: no-preference)`.
- **Calm.** 150 to 400 ms for a change the reader caused; an idle loop slow enough to follow. Nothing flashes more than three times a second.

## Before you finish

- At 360 px and at 1,280 px: nothing overflows, nothing overlaps, every chart is readable.
- Contrast: every text and mark reads against the background it sits on, and every colour comes from a custom property.
- With reduced motion: every animated thing shows its final state.
- Every number on the page is one the sources state.
