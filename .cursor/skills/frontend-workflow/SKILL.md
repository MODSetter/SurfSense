---
name: frontend-workflow
description: Coordinates frontend and UI implementation, refactoring, and review using the project's React performance, shadcn/ui, animation vocabulary, and motion-review skills. Use when the user explicitly requests /frontend-workflow for a frontend task.
disable-model-invocation: true
---

# Frontend Workflow

Use this as the single entry point for frontend work. It orchestrates specialist
skills; it does not duplicate their rules.

## Specialist Skills

Load only the skills relevant to the task:

- **React or Next.js code:** read
  `../vercel-react-best-practices/SKILL.md`, then load only the applicable files
  from its `rules/` directory. Do not load its full compiled guide by default.
- **shadcn/ui components or a project with `components.json`:** read
  `../shadcn/SKILL.md` and follow its project-inspection, component-reuse,
  documentation, composition, styling, and accessibility workflow.
- **A vaguely described motion effect:** read
  `../animation-vocabulary/SKILL.md` first to identify the exact term. This
  glossary names effects; it does not decide whether to build them.
- **Animation or motion code added, changed, or explicitly reviewed:** after
  implementation, read `../review-animations/SKILL.md` and perform its focused
  motion review. Load `../review-animations/STANDARDS.md` only when exact
  values or citations are needed.

Do not load animation skills for frontend work that has no motion concern.

## Workflow

1. **Understand the task**
   - Inspect the relevant implementation and trace the affected interaction.
   - Clarify only decisions that materially change behavior or design.
   - Reuse existing components, helpers, tokens, and patterns.

2. **Select guidance**
   - Apply the specialist-skill conditions above.
   - Read detailed reference files only when the touched code needs them.
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
   - If motion changed, run the animation review only after functional
     implementation is complete and resolve blocking findings within scope.

5. **Report**
   - Summarize the user-visible result, checks run, and unresolved risks.
   - Use the animation review's required findings-and-verdict format only when
     the user requested a review. For implementation tasks, report motion
     findings as part of the normal completion summary.

## Precedence and Conflicts

Resolve conflicting guidance in this order:

1. The user's explicit requirements.
2. Correctness, security, and accessibility.
3. Existing project conventions and configuration.
4. shadcn/ui component and composition rules.
5. React and Next.js performance guidance.
6. Motion polish.

Never sacrifice correctness or accessibility for visual polish or a
micro-optimization. If a specialist rule conflicts with the installed library
version or project configuration, verify the current API and follow the
project's actual version.

## Invocation

Use:

```text
/frontend-workflow <frontend task>
```

Examples:

```text
/frontend-workflow build a responsive settings dialog
/frontend-workflow improve the performance of this React page
/frontend-workflow add the subtle grow-from-trigger effect to this popover
/frontend-workflow review this component's UI and motion
```
