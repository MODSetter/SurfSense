---
name: make-interfaces-feel-better
description: >-
  Design engineering principles for making interfaces feel polished. Use when building UI components, reviewing frontend code, implementing animations, hover states, shadows, borders, typography, icons, micro-interactions, enter/exit animations, or any visual detail work. Supports quick and full review modes. Triggers on UI polish, design details, "make it feel better", "feels off", stagger animations, border radius, optical alignment, font smoothing, tabular numbers, image outlines, box shadows, icons, icon stroke weight, icon states, motion restraint.
---

# Details that make interfaces feel better

Great interfaces rarely come from a single thing. It's usually a collection of small details that compound into a great experience. Apply these principles when building or reviewing UI code. Before suggesting or writing a fix, identify the project's existing styling system and express the change in that system: Tailwind in a Tailwind project, plain CSS in a CSS project, or the established CSS-in-JS approach. Never introduce a second styling system just to apply a polish fix.

When reviewing, slow the interface down: replay motion at 10% speed in the browser's Animations panel and walk every state: hover, focus, active, loading, empty. What feels off at 10% speed is what's subtly wrong at full speed.

## Quick Reference

| Category | When to Use |
| --- | --- |
| [Typography](typography.md) | Text wrapping, font smoothing, tabular numbers |
| [Surfaces](surfaces.md) | Border radius, optical alignment, shadows, image outlines, hit areas |
| [Animations](animations.md) | Interruptible animations, enter/exit transitions, icon animations, scale on press, motion restraint |
| [Icons](icons.md) | Icon stroke weight, states via `currentColor`, outline vs fill, sizing, RTL flipping |
| [Performance](performance.md) | Transition specificity, `will-change` usage |

## Core Principles

### 1. Concentric Border Radius

Outer radius = inner radius + padding. Mismatched radii on nested elements is the most common thing that makes interfaces feel off.

### 2. Optical Over Geometric Alignment

When geometric centering looks off, align optically. Buttons with icons, play triangles, and asymmetric icons all need manual adjustment.

### 3. Shadows for Elevation, Borders for Structure

For buttons, cards, and containers whose border exists only to create depth, prefer layered transparent `box-shadow` values. Keep borders that communicate structure or state: dividers, layout separators, and selected or focus states.

### 4. Interruptible Animations

Use CSS transitions for interactive state changes — they can be interrupted mid-animation. Reserve keyframes for staged sequences that run once.

### 5. Split and Stagger Enter Animations

For an infrequent staged entrance where sequence helps communicate hierarchy, break content into semantic chunks and stagger them by ~100ms instead of animating one container. Do not stagger routine, high-frequency interactions.

### 6. Subtle Exit Animations

Use a small fixed `translateY` instead of full height. Exits should be softer than enters. Use `ease-out` for both enter and exit transitions.

### 7. Contextual Icon Animations

Animate icons with `opacity`, `scale`, and `blur` instead of toggling visibility. Use exactly these values: scale from `0.25` to `1`, opacity from `0` to `1`, blur from `4px` to `0px`. If the project has `motion` or `framer-motion` in `package.json`, match that package's import path (or the established nearby imports when both exist) and use `transition: { type: "spring", duration: 0.3, bounce: 0 }` — bounce must always be `0`. If no motion library is installed, keep both icons in the DOM (one absolute-positioned) and cross-fade with CSS transitions using `cubic-bezier(0.2, 0, 0, 1)` — this gives both enter and exit animations without any dependency.

### 8. Font Smoothing

Apply `-webkit-font-smoothing: antialiased` to the root layout on macOS for crisper text.

### 9. Tabular Numbers

Use `font-variant-numeric: tabular-nums` for any dynamically updating numbers to prevent layout shift.

### 10. Text Wrapping

Use `text-wrap: balance` on headings. Use `text-wrap: pretty` for body text to avoid orphans.

### 11. Image Outlines

Add a subtle `1px` outline with low opacity to images for consistent depth. The color must be pure black in light mode (`oklch(0 0 0 / 0.1)`) and pure white in dark mode (`oklch(1 0 0 / 0.1)`), never a near-black like slate, zinc, or any tinted neutral. A tinted outline picks up the surface color underneath it and reads as dirt on the image edge.

### 12. Scale on Press

A subtle `scale(0.96)` on click gives buttons tactile feedback. Always use `0.96`. Never use a value smaller than `0.95` — anything below feels exaggerated. Add a `static` prop to disable it when motion would be distracting.

### 13. Skip Animation on Page Load

Use `initial={false}` on `AnimatePresence` to prevent enter animations on first render. Verify it doesn't break intentional entrance animations.

### 14. Never Use `transition: all`

Always specify exact properties: `transition-property: scale, opacity`. Tailwind's `transition-transform` covers `transform, translate, scale, rotate`.

### 15. Use `will-change` Sparingly

Only for `transform`, `opacity`, `filter` — properties the GPU can composite. Never use `will-change: all`. Only add when you notice first-frame stutter.

### 16. Minimum Hit Area

Interactive elements should prefer a 44×44px hit area for touch or mobile contexts. In dense desktop interfaces, use at least 40×40px. Extend with a pseudo-element if the visible element is smaller. Never let hit areas of two elements overlap.

### 17. Match Icon Stroke to Text Weight

An icon next to text carries the text's optical weight: `1.5px` stroke beside regular (400) text, `2px` beside semibold (600). One stroke weight per icon set; never mix libraries on one surface.

### 18. One SVG, Recolored per State

Icons use `currentColor` and get their states (hover, selected, disabled) from CSS color and opacity, never from separate assets. Outline variant is the default; fill variant marks the active state.

### 19. Motion Restraint

No custom animation on high-frequency interactions: the attention cost repeats on every trigger. Motion is never the only feedback channel; every animated state change also needs a static cue such as color, icon, or label.

## Common Mistakes

| Mistake | Fix |
| --- | --- |
| Same border radius on parent and child | Calculate `outerRadius = innerRadius + padding` |
| Icons look off-center | Adjust optically with padding or fix SVG directly |
| Border used only to fake elevation | Use layered `box-shadow` with transparency; keep structural and state borders |
| Jarring staged entrance or contextual exit | Stagger infrequent entrances and keep context-preserving exits subtle |
| Numbers cause layout shift | Apply `tabular-nums` |
| Heavy text on macOS | Apply `antialiased` to root |
| Animation plays on page load | Add `initial={false}` to `AnimatePresence` |
| `transition: all` on elements | Specify exact properties |
| First-frame animation stutter | Add `will-change: transform` (sparingly) |
| Tiny hit areas on small controls | Extend with a pseudo-element to 44×44px for touch/mobile, or at least 40×40px in dense desktop UI |
| Hairline icon beside bold text | Match the stroke width to the text weight |
| Separate icon assets per state | One `currentColor` SVG, states via CSS |
| Filled icons everywhere | Outline as default, fill only for the active state |
| Entrance animation on every hover or keystroke | Instant feedback or ≤150ms opacity/color transition |

## Review Output Format

Use `full` when no review mode is supplied.

| Mode | Coverage | Finding cap |
| --- | --- | --- |
| `quick` | Primary user path and highest-traffic states; report only `HIGH` and `MEDIUM` issues | 5 |
| `full` | Entire requested scope across typography, surfaces, animations, icons, and performance | 15 |

### Scope and Coverage

State the mode, exact scope, framework, styling conventions, and any review boundary. Show what was actually inspected:

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Files, components, states, or checks | Findings count, `Clear`, or `Not reviewed` with a reason |

Include all five Quick Reference categories. Never imply an uninspected surface was reviewed.

### Findings

Group findings by principle. Use a markdown table with **Severity**, **Location**, **Before**, **After**, and **Why** columns. Include every change made or proposed, not a subset. Never use separate "Before:" / "After:" lines.

- **Severity**: `HIGH` makes an interaction inaccessible, misleading, unreadable, or repeatedly disruptive; `MEDIUM` creates a noticeable usability or consistency problem; `LOW` is isolated polish and appears only in `full` mode.
- **Location**: cite `path/to/file:line`. If the artifact has no source files, cite the exact screen and component instead.
- **Before / After**: show the current implementation and an actionable replacement.
- **Why**: name the violated principle and explain its user impact.

Consolidate a repeated systemic issue into one row and list every affected location. Omit principles with no findings and never pad the report to reach the cap.

### Example

#### Concentric border radius
| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| LOW | `src/Card.tsx:28` | `rounded-xl` on card + `rounded-xl` on inner button (`p-2`) | `rounded-2xl` on card (`8 + 8 = 16`), `rounded-lg` on inner button | Nested corners should be concentric |
| LOW | `src/card.css:11` | `border-radius: 16px` on both nested surfaces | Outer `24px`, inner `16px` with `8px` padding | Equal nested radii make the inner surface look pinched |

#### Tabular numbers
| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| MEDIUM | `src/Counter.tsx:17` | `<span>{count}</span>` | `<span className="tabular-nums">{count}</span>` | Proportional digits cause changing values to shift |
| LOW | `src/timer.css:8` | Default numerals on a timer | Add `font-variant-numeric: tabular-nums` to the timer | Equal-width digits keep the timer stable |

#### Scale on press
| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| LOW | `src/Button.tsx:19` | `<button className="...">` | Add `active:scale-[0.96] transition-transform` | Press feedback makes the control feel responsive |
| MEDIUM | `src/button.css:24` | `scale(0.9)` on press | Raise to `scale(0.96)` | Anything below `0.95` feels exaggerated |

### Considered but Rejected

Include 1–3 real candidates in `quick` mode and 2–5 in `full` mode:

| Location | Candidate | Rejected because |
| --- | --- | --- |
| `src/Card.tsx:28` | Increase the shadow | Existing depth matches the shared surface token; changing one card would reduce consistency |

Do not invent filler. If the scope contains fewer borderline candidates, include the ones that exist and say so.

### Verification and Verdict

After the findings:

1. **Verification**: list the exact commands or interactions run and their observed results. Walk every relevant state and inspect motion at 10% speed when animation is involved. If a check was not run, label it **Not verified** and state what remains.
2. **Verdict**: `Block` if any `HIGH` finding remains, `Needs changes` if only `MEDIUM` or `LOW` findings remain, and `Approve` only when no actionable findings remain. List every unverified check beside the verdict.

When there are no findings, omit the findings table, state "No actionable interface-polish findings", report verification and rejected candidates, and end with `Approve`.
