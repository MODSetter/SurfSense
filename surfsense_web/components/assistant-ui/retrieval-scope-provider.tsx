"use client";

import { getDefaultStore, useAtomValue } from "jotai";
import {
	createContext,
	type ReactNode,
	useCallback,
	useContext,
	useEffect,
	useRef,
	useState,
} from "react";
import { retrievalScopeAtom } from "@/atoms/chat/retrieval-scope.atom";
import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import type { RetrievalScope } from "@/contracts/types/retrieval-scope.types";
import { persistRetrievalScopeCookie } from "@/lib/chat/retrieval-scope-preferences";

type RetrievalScopeContextValue = {
	scope: RetrievalScope;
	setScope: (scope: RetrievalScope) => void;
};

const RetrievalScopeContext = createContext<RetrievalScopeContextValue | null>(null);
const jotaiStore = getDefaultStore();

export function RetrievalScopeProvider({
	children,
	initialScope,
	workspaceId,
}: {
	children: ReactNode;
	initialScope: RetrievalScope;
	workspaceId: number;
}) {
	const [scope, setScopeState] = useState(initialScope);
	const { data: currentUser } = useAtomValue(currentUserAtom);
	const pendingPersistence = useRef(false);

	useEffect(() => {
		jotaiStore.set(retrievalScopeAtom, scope);
	}, [scope]);

	useEffect(() => {
		if (!currentUser?.id || !pendingPersistence.current) return;
		pendingPersistence.current = false;
		persistRetrievalScopeCookie(currentUser.id, workspaceId, scope);
	}, [currentUser?.id, scope, workspaceId]);

	const setScope = useCallback(
		(nextScope: RetrievalScope) => {
			setScopeState(nextScope);
			jotaiStore.set(retrievalScopeAtom, nextScope);
			pendingPersistence.current = !currentUser?.id;
			persistRetrievalScopeCookie(currentUser?.id, workspaceId, nextScope);
		},
		[currentUser?.id, workspaceId]
	);

	return (
		<RetrievalScopeContext.Provider value={{ scope, setScope }}>
			{children}
		</RetrievalScopeContext.Provider>
	);
}

export function useRetrievalScope(): RetrievalScopeContextValue {
	const value = useContext(RetrievalScopeContext);
	if (!value) throw new Error("useRetrievalScope must be used within RetrievalScopeProvider");
	return value;
}
