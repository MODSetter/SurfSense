import { atom } from "jotai";
import type { GetConnectorsRequest } from "@/contracts/types/connector.types";

export const globalConnectorsQueryParamsAtom = atom<GetConnectorsRequest["queryParams"]>({
	skip: 0,
	limit: 10,
});
