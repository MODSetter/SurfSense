import { atom } from "jotai";
import type { GetDocumentsRequest } from "@/contracts/types/document.types";

export const globalDocumentsQueryParamsAtom = atom<GetDocumentsRequest["queryParams"]>({
	page_size: 10,
	page: 0,
});
