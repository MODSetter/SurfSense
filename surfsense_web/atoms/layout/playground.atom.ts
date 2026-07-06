import { atom } from "jotai";

/**
 * Whether the second-level API Playground sidebar is open. Toggled by the
 * Playground nav button and kept in memory for the session, so it survives
 * in-app navigation (opening a new chat won't close it) and only closes when
 * the user clicks the toggle. It defaults to open, so a fresh app load — a new
 * signup or a relogin — always starts with the playground visible.
 */
export const playgroundSidebarOpenAtom = atom<boolean>(true);
