---
name: frontend-workflow
description: Frontend and UI work in surfsense_web and surfsense_local/frontend — building, refactoring, styling, animating, or reviewing React and Next.js components, shadcn/ui, color tokens and themes, visual polish, and motion. Load this first for any UI task, including adding or changing a shadcn/ui component (dialog, button, dropdown, form, sidebar, table) in a tree with components.json — it owns the color palette, polish rules, and the precedence order, then routes to the separate shadcn skill for component wiring and the CLI. Use for any frontend component, page, style, animation, hover state, icon, layout, or UI review task.
---

# Frontend Workflow

Single entry point for frontend work in `surfsense_web` and
`surfsense_local/frontend`. Both are React + Tailwind + shadcn/ui with their own
`components.json`. Detect which tree the task touches, and treat that tree's
`package.json`, `components.json`, and styling setup as authoritative. All
guidance lives in this skill's own folders; load only what the task touches.

## Reference Map

| Read this | When |
|---|---|
| [react-performance/SKILL.md](./react-performance/SKILL.md) | React or Next.js code — components, pages, data fetching, bundles, re-renders |
| [../shadcn/SKILL.md](../shadcn/SKILL.md) | shadcn/ui components, or any project with `components.json`. Separate skill — it inspects the project live and grants its own CLI. |
| [base-ui.md](./base-ui.md) | Components in `surfsense_local/frontend` — composition, menus, dialogs, tooltips, tabs, and testing them on Base UI |
| [color/SKILL.md](./color/SKILL.md) | Colors, themes, charts, design tokens, borders, shadows |
| [polish/SKILL.md](./polish/SKILL.md) | Typography, surfaces, icons, micro-interactions, enter/exit transitions |
| [motion/apple-design.md](./motion/apple-design.md) | Gesture-driven or physical motion — drag, swipe, sheets, springs, momentum, interruptible transitions, translucent materials |

Each entry is an index. Open its supporting files only when the touched code
needs them:

- `react-performance/rules/` holds one file per rule. Load the applicable ones.
  `react-performance/rules-compiled.md` is the same rules compiled into one
  document — do not load it by default.
- `polish/` splits into `typography.md`, `surfaces.md`, `animations.md`,
  `icons.md`, `performance.md`.
- `../shadcn/rules/` splits by concern; `../shadcn/cli.md`, `registry.md`,
  `customization.md` cover tooling and theming.
- `color/PALETTE.css` is the canonical palette contract.

Do not load motion references for work with no motion concern.
Apple-style motion is for gesture, physics, and material work; a hover state or
a color change does not need it.

## Workflow

1. **Understand the task**
   - Inspect the relevant implementation and trace the affected interaction.
   - Clarify only decisions that materially change behavior or design.
   - Reuse existing components, helpers, tokens, and patterns.

2. **Select guidance**
   - Use the reference map above.
   - Read detailed files only when the touched code needs them.
   - Treat current project configuration and installed APIs as authoritative.

3. **Implement**
   - Make the smallest complete change that satisfies the request.
   - Preserve established visual language and component APIs.
   - Cover loading, empty, error, disabled, responsive, keyboard, focus, and
     reduced-motion states when they are relevant.

4. **Validate**
   - Run the smallest relevant lint, type, and test checks.
   - For visible interaction changes, verify the rendered behavior when a
     runnable frontend is available.
   - If visual details or motion changed, apply the polish review only after
     functional implementation is complete and resolve blocking findings
     within scope.

5. **Report**
   - Summarize the user-visible result, checks run, and unresolved risks.
   - Use the polish review format only when the user requested a review. For
     implementation tasks, include relevant visual or motion findings in the
     normal completion summary.

## Precedence and Conflicts

Resolve conflicting guidance in this order:

1. The user's explicit requirements.
2. Correctness, security, and accessibility.
3. Existing project conventions and configuration.
4. The canonical color system and shadcn/ui composition rules.
5. React and Next.js performance guidance.
6. Motion behavior for gesture-driven and interruptible interactions.
7. Interface and motion polish.

Specific overlaps:

- **Icons** — `../shadcn/rules/icons.md` governs icon usage inside shadcn
  components (`data-icon`, sizing, passing icons as objects). `polish/icons.md`
  governs stroke weight, optical detail, states via `currentColor`, and RTL
  flipping. Apply the shadcn rule to component wiring, the polish rule to
  visual detail.
- **Color** — `color/SKILL.md` and `color/PALETTE.css` are canonical. Where
  `../shadcn/rules/styling.md` or `../shadcn/customization.md` describe theming,
  follow them for mechanism and the palette for values.
- **Motion** — `motion/apple-design.md` governs how motion behaves;
  `polish/animations.md` governs concrete values and static detail. Where they
  conflict, prefer springs and current-value interpolation for anything the
  user can touch or interrupt, and CSS transitions for everything else.

Never sacrifice correctness or accessibility for visual polish or a
micro-optimization. If a rule conflicts with the installed library version or
project configuration, verify the current API and follow the project's actual
version.

## Notes

The `SKILL.md` and `.md` files inside `react-performance/`, `color/`, `polish/`,
and `motion/` retain their original frontmatter from when they were separate
skills. That frontmatter is inert here — these are reference files, not
independently discovered skills. Read their bodies and ignore their
`name`, `description`, and invocation fields.
