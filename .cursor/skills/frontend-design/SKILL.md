---
name: frontend-design
description: Build distinctive, production-quality UI. Use when creating or reshaping user-facing interfaces, components, pages, layouts, visual redesigns, responsive behavior, loading/error/empty states, or accessibility-sensitive frontend work.
---

# Frontend Design & UI Quality

Approach this as the design lead at a small studio known for giving every client a visual identity that could not be mistaken for anyone else's. Make deliberate, opinionated choices about palette, typography, layout, motion, and copy that are specific to the brief, then execute them with engineering rigor: accessible, responsive, performant, and complete in every state.

## 1. Aesthetic Direction

### Ground It In The Subject

If the brief does not pin down the product or subject, pin it yourself before designing: name one concrete subject, its audience, and the page's single job. Use the user's preferences, project context, and previous design choices as hints. The subject's world - its materials, instruments, artifacts, and vernacular - is where distinctive choices come from. Build with real or realistic content throughout. Never use lorem ipsum; placeholder text hides wrapping, overflow, hierarchy, and tone problems.

### Design Principles

For web designs, the hero is a thesis. Open with the most characteristic thing in the subject's world: a headline, image, animation, live demo, interactive moment, or concrete product artifact. A big number with a small label, supporting stats, and a gradient accent is the template answer; only use it if it is truly the best option.

Typography carries personality. Pair display and body faces deliberately, not the same families you would reach for on every project. Set a clear type scale with intentional weights, widths, spacing, and rhythm. Respect semantic hierarchy: one `h1` per page, no skipped heading levels, and no heading styles on non-heading content.

Structure is information. Numbering, eyebrows, dividers, labels, cards, and section breaks should encode something true about the content, not decorate it. Numbered markers like `01 / 02 / 03` only belong when the content is actually sequential.

Leverage motion deliberately. One orchestrated moment usually lands harder than scattered effects. Always respect `prefers-reduced-motion`.

Match complexity to the vision. Maximalist directions need elaborate execution; minimal directions need precision in spacing, type, and detail. Elegance is executing the chosen vision well.

### Known AI Defaults

Avoid defaulting to: warm cream + high-contrast serif + terracotta; near-black + acid green/vermilion; broadsheet layouts with hairline rules; purple/indigo everything; decorative gradients; `rounded-2xl` everywhere; generic hero sections; uniform card grids that ignore information priority; oversized equal padding; layered shadows. These can be valid when the brief calls for them, but they must be choices, not reflexes.

### Existing Product Rule

If the project already has a design system, tokens, components, palette, radius scale, or layout language, that system is the brief. Distinctiveness then lives in hierarchy, composition, content, interaction, and motion - not in inventing stray colors or one-off radii. Use semantic tokens, existing components, and the established spacing scale. Avoid raw hex values or off-scale spacing unless the design system itself requires them.

## 2. Process

Work in two passes.

First, create a compact design plan:

- **Color:** 4-6 named hex values for greenfield work, or the exact tokens to use in an existing product.
- **Type:** roles for display, body, and utility/caption text.
- **Layout:** one-sentence concept plus quick ASCII wireframes when useful.
- **Signature:** the single element this interface should be remembered by.

Second, critique the plan against the brief before building. If any part could appear unchanged in a generic page for a different subject, revise it. Only then write code. Derive every visual choice from the revised plan or the existing design system.

When writing CSS, watch selector specificity. Generated class names often cancel each other out around section spacing, component padding, and element selectors. Prefer simple, local class structure and design-system utilities over clever selector chains.

## 3. Engineering The Design

### Components

- Prefer composition over configuration: structured children over prop grab-bags.
- Keep components focused; split anything past roughly 200 lines unless there is a strong local reason not to.
- Separate data fetching from presentation. Containers resolve loading/error/empty and pass clean data to presentational components.
- Choose the simplest state that works: `useState` for component UI state; lifted state for 2-3 siblings; context for read-heavy/write-rare concerns like theme, auth, locale; URL state for shareable filters/pagination; SWR/React Query for server data; global stores only for genuinely app-wide client state.
- Avoid prop drilling past 3 levels. Restructure or introduce context when intermediate components do not use the props.

### Four UI States

Design loading, error, empty, and success together.

- **Loading:** use skeletons that match content shape for content areas. Add `aria-busy="true"` where appropriate.
- **Error:** say what went wrong and how to fix it. Offer retry when retrying can work.
- **Empty:** treat it as an invitation to act: icon or marker, short explanation, and a primary action. Never leave a blank region. Use `role="status"` when the empty state announces a result.
- **Success:** optimize the default path without hiding constraints, secondary actions, or overflow cases.

Use optimistic updates for quick mutations where rollback is cheap and failure is understandable.

### Accessibility

Meet WCAG 2.1 AA as a floor.

- Use native elements first: `button`, `a`, `label`, `input`, `select`, `textarea`, `dialog`.
- A clickable `div` needs `role`, `tabIndex`, and keyboard handling for Enter/Space; prefer a real `button`.
- Every icon-only control needs an `aria-label`. Every input needs a visible label or explicit accessible name.
- Focus must be visible. Dialogs and popovers move focus on open and restore it on close; modal dialogs trap focus.
- Contrast: 4.5:1 for normal text, 3:1 for large text and non-text UI indicators.
- Do not use color as the only state indicator. Pair color with text, iconography, shape, or pattern.
- Respect `prefers-reduced-motion` for animation and transitions.

### Responsive

Design mobile-first, then expand. Verify at 320px, 768px, 1024px, and 1440px. Check text wrapping, overflow, touch targets, sticky elements, modals, tables, and long localized strings, not just whether the layout stacks.

## 4. Restraint And Self-Critique

Spend boldness in one place. Let the signature element be the memorable move; keep everything around it quiet and disciplined. Cut decoration that does not serve the brief. Not taking a risk can also be a risk.

Critique the work visually as you build. If screenshots are available, use them. Before presenting, remove one accessory: one extra border, glow, gradient, icon, animation, card, or label that weakens the hierarchy.

## 5. Writing In The Design

Words make the interface easier to understand and use. They are design material, not decoration.

Write from the end user's side of the screen. Name things by what people control and recognize, not by internal implementation. A person manages notifications, not webhook config. Be specific rather than clever.

Use active voice. A control says exactly what happens: "Save changes," not "Submit." Keep action vocabulary consistent through the whole flow: "Publish" leads to "Published."

Treat failure and emptiness as moments for direction, not mood. Errors do not apologize and are never vague. Empty states invite the next action.

Keep copy conversational and tuned: plain verbs, sentence case, no filler, with tone matched to the brand and audience. Each element does one job: a label labels, an example demonstrates, helper text helps.

## Verification Checklist

Before presenting UI work, verify:

- [ ] Design direction is specific to the brief, not a generic default.
- [ ] Existing design-system tokens, spacing, components, and typography are respected.
- [ ] Realistic content, loading, error, empty, and success states are handled.
- [ ] Keyboard navigation, focus, labels, contrast, and reduced motion are covered.
- [ ] Layout works at 320px, 768px, 1024px, and 1440px with no obvious overflow.
