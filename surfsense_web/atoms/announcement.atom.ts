import { atomWithStorage } from "jotai/utils";

// Atom to track whether the announcement banner has been dismissed
// Persists to localStorage automatically
export const announcementDismissedAtom = atomWithStorage("surfsense_announcement_dismissed", false);
