import { atom } from "jotai";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";

export const globalDocumentsQueryParamsAtom = atom<GetDocumentsRequest["queryParams"]>({
	page_size: 10,
	page: 0,
});

/**
 * Whether the Documents panel is open. Shared so the Composer can toggle the
 * same surface the sidebar's Documents button controls.
 */
export const documentsSidebarOpenAtom = atom(true);

export interface AgentCreatedDocument {
	id: number;
	title: string;
	documentType: string;
	workspaceId: number;
	folderId: number | null;
	createdById: string | null;
	createdAt: number;
}

export const agentCreatedDocumentsAtom = atom<AgentCreatedDocument[]>([]);
