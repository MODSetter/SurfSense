---
name: color-system
description: Applies and reviews SurfSense's canonical light and dark color palette, semantic design tokens, typography, charts, borders, shadows, and theme mappings. Use when creating or changing frontend colors, themes, component styling, data visualizations, or design tokens.
disable-model-invocation: true
---

# SurfSense Color System

Use [PALETTE.css](PALETTE.css) as the canonical palette contract. Preserve its
token names and values unless the user explicitly requests a palette change.

## Principles

1. Use semantic tokens such as `background`, `foreground`, `primary`,
   `muted`, `accent`, `destructive`, `border`, and their foreground pairs.
   Do not use raw hex values in components.
2. Use the matching foreground token for text and icons placed on a semantic
   surface: `primary-foreground` on `primary`, `card-foreground` on `card`,
   and so on.
3. Use `chart-1` through `chart-5` for data series. Do not repurpose chart
   colors as component state colors.
4. Use `ring` for focus indicators and `border` or `input` for boundaries.
   Never remove a visible keyboard focus indicator.
5. Use `muted-foreground` only for secondary text. Do not use it for small or
   essential text unless its contrast passes WCAG.
6. Use `destructive` only for destructive actions, errors, or dangerous
   states. Do not use chart colors to communicate errors.
7. Support both `:root` and `.dark`; never add a light-only semantic token.
8. Prefer existing semantic tokens over creating new aliases. Add a token only
   when it represents a reusable semantic role that the palette does not cover.

## Workflow

1. Locate the active global CSS file from the target app's `components.json`;
   this repository contains more than one frontend.
2. Compare the active theme with [PALETTE.css](PALETTE.css). Do not overwrite
   unrelated CSS, animation, layout, or framework directives.
3. Apply palette values at the global token layer, not inside individual
   components.
4. In components, use the project's semantic utility classes or CSS variables,
   for example `bg-background text-foreground`, `bg-card
   text-card-foreground`, and `border-border`.
5. Check affected foreground/background pairs in both themes. WCAG targets:
   4.5:1 for normal text, 3:1 for large text and meaningful UI boundaries.
6. Verify focus, hover, active, selected, disabled, destructive, chart, and
   sidebar states when affected.

## Guardrails

- Do not invent intermediate shades to make one component look better.
- Do not use opacity to compensate for an incorrect semantic token when it
  reduces text contrast.
- Do not replace the palette wholesale when the requested change concerns one
  component.
- Report a contrast failure instead of silently changing canonical values.
- Treat the palette's `@theme inline` block as Tailwind v4 configuration.
  Before applying it, verify the target app uses Tailwind v4 and preserve any
  required non-color namespaces already present in its global stylesheet.

## Known Accessibility Constraint

The canonical dark `muted-foreground` (`#7a706a`) does not reach 4.5:1 for
normal text on dark `background` (4.11:1), `card` (3.90:1), or `muted`
(3.64:1). Preserve the palette, but do not use this token for essential or
small normal-weight dark-mode text. Report the conflict and request a palette
decision when no existing foreground token fits.

## Coordination

- For shadcn/ui composition and styling, also use `../shadcn/SKILL.md`.
- For React or Next.js implementation, also use
  `../vercel-react-best-practices/SKILL.md`.
- For interface polish, color transitions, or reduced-motion behavior, use
  `../make-interfaces-feel-better/SKILL.md` after implementation.

## Output

For implementation tasks, report:

- which app and global stylesheet received the palette;
- whether both themes were updated;
- contrast or state risks that remain;
- validation performed.

For audits, cite each issue by token pair and usage location, then recommend a
semantic-token correction before proposing a new color.
