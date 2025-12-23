"use client";

import { atom } from "jotai";

/**
 * Atom to store the IDs of documents mentioned in the current chat composer.
 * This is used to pass document context to the backend when sending a message.
 */
export const mentionedDocumentIdsAtom = atom<number[]>([]);

