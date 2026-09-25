# project

2026-09-25, whole-project migration of `surfsense_local/frontend` from `radix-ui` 1.6.7 to `@base-ui/react` 1.8.0. Golden pairs (radix-nova → base-nova, three-way merge) for the shadcn wrappers; engine for `tabs`, `stepper`, `combobox`. 0 wrappers remain on Radix.

## Changed

- `package.json`, `pnpm-lock.yaml`: `@base-ui/react` ^1.8.0 added; `radix-ui` removed.
- `components.json`: `style` `radix-nova` → `base-nova`, so `shadcn add` now delivers Base UI components.
- 17 files in `src/components/ui/`: see the per-component reports.
- App-code sweep: 26 `asChild` → `render` on our wrappers; 20 menu `onSelect` → `onClick`; 5 Radix focus callbacks → `initialFocus`/`finalFocus`; `data-[state=open|active]` classes → `data-popup-open`/`data-active`; a menu label moved into its group (Base UI throws otherwise); the download link rebuilt as a real `<a>`.
- Tests: menu items found with `findByRole` (Base UI mounts popups asynchronously after a pointer click); tooltips found by text (Base UI tooltips have no role); the modal layout test waits for Base UI's overflow lock instead of react-remove-scroll's attribute.
- `src/test-setup.ts` (new), `vite.config.ts` `test.setupFiles`: stubs `Element.getAnimations` for jsdom.
- Final checks against the baseline: typecheck clean (baseline clean); 258/258 tests, no unhandled errors (baseline 258/258); lint clean (baseline clean); `pnpm build` succeeds.

## Left alone

- assistant-ui primitives (`ComposerPrimitive.Send/Cancel`, `ActionBarPrimitive.Copy`, `ThreadPrimitive.ScrollToBottom`) keep their own `asChild`: not Radix wrappers.
- `sonner`, `select.tsx` (a native `<select>`), `progress.tsx` (plain divs): no Radix.
- `onSelect` props on `FormatCard`, `LeftSidebar` and the workspace list: app props, not menu items.
- `"use client"` directives that base-nova adds were kept; they are inert in this Vite app.

## Behavior changes

- Tooltips are visual only: no `role="tooltip"` or `aria-describedby` (tooltip.md).
- Tabs activate on Enter/Space, not on arrow focus (tabs.md).
- The scroll area's scrollbar is visible whenever content overflows, not just on hover (scroll-area.md).
- Separators now carry `role="separator"` (separator.md).
- Menu focus loops; popups mount a tick later after a pointer click (dropdown-menu.md).
- Kept on purpose, departing from base-nova: `AlertDialogAction` still closes the dialog unless the click handler calls `preventDefault()`; the model picker's radio items close on pick.

## Verify by hand

- Run through the per-component checklists in the Electron app on macOS, especially dialogs (focus and title bar), the model picker, the workspace context menu, and the provider combobox.
