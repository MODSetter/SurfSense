import { atom } from "jotai";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";

export const globalDocumentsQueryParamsAtom = atom<GetDocumentsRequest["queryParams"]>({
	page_size: 10,
	page: 0,
});

export const documentsSidebarOpenAtom = atom(false);

export interface AgentCreatedDocument {
	id: number;
	title: string;
	documentType: string;
	searchSpaceId: number;
	folderId: number | null;
	createdById: string | null;
}

export const agentCreatedDocumentsAtom = atom<AgentCreatedDocument[]>([]);
