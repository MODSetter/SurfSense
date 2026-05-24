import { atom } from "jotai";

/**
 * Tick counter that increments each time a sidebar slide-out panel opens.
 * Consumers read this with `useAtomValue` and store the last-seen value in
 * a ref so the effect fires only when the tick changes. This preserves the
 * one-shot semantics of the previous window-event implementation: a
 * subscriber that mounts after a panel has already opened does not
 * retroactively re-trigger.
 */
export const slideoutOpenedTickAtom = atom(0);
