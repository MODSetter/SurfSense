import { atom } from "jotai";
import {
	DEFAULT_RETRIEVAL_SCOPE,
	type RetrievalScope,
} from "@/contracts/types/retrieval-scope.types";

/** Engine mirror of the server-seeded React preference. */
export const retrievalScopeAtom = atom<RetrievalScope>(DEFAULT_RETRIEVAL_SCOPE);

/** Immutable submit-time snapshot consumed once by startNewChat. */
export const submittedRetrievalScopeAtom = atom<RetrievalScope | null>(null);
