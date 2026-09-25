# dialog

2026-09-25, golden pair. `Overlay` → `Backdrop`, `Content` → `Popup`.

## Changed

- `src/components/ui/dialog.tsx`: base-nova shape; kept the local `XIcon` and translated "Close" strings (`app_dialog_close_aria`, `app_dialog_footer_close_button`).
- `chats-dialog.tsx`, `workspace-rail.tsx`: `onOpenAutoFocus` (preventDefault + focus/select input) → `initialFocus={() => { input.select(); return input }}`; the chats search uses `initialFocus={searchRef}`.
- `settings-dialog.tsx`, `studio-panel.tsx`: `asChild` → `render`.
- `modal-layout.test.tsx`: waited for react-remove-scroll's `data-scroll-locked`. It now waits for the page's `overflow: hidden` lock, and compares body padding numerically (jsdom reports `"0"`).
- Leftover scan clean: `grep -n "radix-ui\|@radix-ui"` finds nothing in this component's files.

## Left alone

- Nothing related.

## Behavior changes

- Scroll lock: Radix's react-remove-scroll added body padding for the scrollbar. Base UI sets `overflow: hidden` + `scrollbar-gutter`. With macOS overlay scrollbars only `overflow` changes. The Electron title-bar spacing stays on `#root` (the layout test covers this).

## Verify by hand

- Open Settings: focus lands inside; Esc closes; focus returns to the Settings button.
- Rename a workspace or chat: the name field is focused with its text selected.
- Open Chats: the search field is focused.
- With a dialog open, the page behind does not scroll and the macOS title bar does not shift.
