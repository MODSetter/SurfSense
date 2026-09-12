# Frontend Design
Act as a design lead, not a template assembler. Root each brief's identity in
its subject, audience, and purpose; choose color, type, composition, motion,
interaction, and language deliberately.

## Start with the subject

Name the concrete subject, intended audience, and primary job. Draw visual
ideas from that world's materials, tools, culture, data, and vocabulary.

Use realistic content; filler conceals wrapping, density, hierarchy, overflow,
and tone problems.

## Establish a direction

Work in two passes. First, define a compact design plan:

- Color: choose 4–6 named hex colors with clear roles and sufficient contrast.
- Type: choose one or two purposeful families and assign display, body, and
  utility roles with an intentional scale.
- Layout: describe the organizing idea, alignment, density, and responsive
  behavior; sketch alternatives with a small ASCII wireframe when useful.
- Signature: choose one memorable interaction or visual move tied to the
  subject, then keep the surrounding design disciplined.

Second, challenge the plan. If it could be reused unchanged for an unrelated
brief, revise the generic parts before building.

## Compose with intent

- Lead with the most characteristic element: a strong headline, live result,
  image, demonstration, or interaction—not an automatic hero formula.
- Keep body lines readable, hierarchy obvious, and heading levels meaningful.
- Use cards, borders, labels, dividers, and numbering only when they explain
  grouping, sequence, priority, or state.
- Let one family or two clearly contrasting families carry the personality;
  avoid isolated italic words, decorative all-caps labels, and needless
  eyebrow text.
- Prefer motion that explains an action or change. Avoid animating every card
  or repeating the same fade-and-slide entrance across the page.

## Avoid generated-looking defaults

Do not reflexively use purple gradients, warm cream with terracotta, black with
acid accents, newspaper grids, identical rounded cards, uniform soft shadows,
monospace metadata, oversized empty spacing, or decorative arrows. Any of
these can work when the subject genuinely calls for it; none is a default.

## Build to a quality floor

- Use semantic structure and native controls. Give every input and icon-only
  action an accessible name and every interaction visible keyboard focus.
- Meet readable contrast, never communicate state through color alone, and
  respect `prefers-reduced-motion`.
- Verify narrow and wide layouts, long text, touch targets, sticky elements,
  tables, and overflow—not merely whether columns stack.
- Design loading, error, empty, and success states together. Make failures
  explain recovery and empty states invite a useful next action.
- Keep CSS selectors local and predictable; avoid specificity collisions.

## Write as part of the interface

Use direct, conversational language from the user's perspective. Controls say
what happens, labels only label, and helper text only helps. Keep action names
consistent through confirmations and errors. Never use cleverness where a
specific explanation would be clearer.

## Critique the result
Review at multiple sizes. Confirm the signature serves the subject, then remove
one accessory that weakens hierarchy.
