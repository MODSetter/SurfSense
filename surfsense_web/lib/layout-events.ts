import { atom } from "jotai";

/**
 * Tick counter that increments each time a sidebar slide-out panel opens.
 * Consumers read this with `useAtomValue` and react to it changing — guard
 * the initial render with a ref so the effect only fires on subsequent
 * opens, matching the one-shot semantics of the previous window event.
 */
export const slideoutOpenedTickAtom = atom(0);
