import { atom } from "jotai";
import type { InboxItem } from "@/contracts/types/inbox.types";

/**
 * Shared atom for status inbox items populated by LayoutDataProvider.
 * Avoids duplicate useInbox("status") calls in child components like ConnectorPopup.
 */
export const statusInboxItemsAtom = atom<InboxItem[]>([]);
