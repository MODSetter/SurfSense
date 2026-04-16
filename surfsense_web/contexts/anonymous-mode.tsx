"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { anonymousChatApiService } from "@/lib/apis/anonymous-chat-api.service";

export interface AnonymousModeContextValue {
	isAnonymous: true;
	modelSlug: string;
	setModelSlug: (slug: string) => void;
	uploadedDoc: { filename: string; sizeBytes: number } | null;
	setUploadedDoc: (doc: { filename: string; sizeBytes: number } | null) => void;
	resetKey: number;
	resetChat: () => void;
}

interface AuthenticatedContextValue {
	isAnonymous: false;
}

type ContextValue = AnonymousModeContextValue | AuthenticatedContextValue;

const DEFAULT_VALUE: AuthenticatedContextValue = { isAnonymous: false };

const AnonymousModeContext = createContext<ContextValue>(DEFAULT_VALUE);

export function AnonymousModeProvider({
	initialModelSlug,
	children,
}: {
	initialModelSlug: string;
	children: ReactNode;
}) {
	const [modelSlug, setModelSlug] = useState(initialModelSlug);
	const [uploadedDoc, setUploadedDoc] = useState<{ filename: string; sizeBytes: number } | null>(
		null
	);
	const [resetKey, setResetKey] = useState(0);

	const resetChat = () => setResetKey((k) => k + 1);

	useEffect(() => {
		anonymousChatApiService
			.getDocument()
			.then((doc) => {
				if (doc) {
					setUploadedDoc({ filename: doc.filename, sizeBytes: doc.size_bytes });
				}
			})
			.catch(() => {});
	}, []);

	const value = useMemo<AnonymousModeContextValue>(
		() => ({
			isAnonymous: true,
			modelSlug,
			setModelSlug,
			uploadedDoc,
			setUploadedDoc,
			resetKey,
			resetChat,
		}),
		[modelSlug, uploadedDoc, resetKey]
	);

	return <AnonymousModeContext.Provider value={value}>{children}</AnonymousModeContext.Provider>;
}

export function useAnonymousMode(): ContextValue {
	return useContext(AnonymousModeContext);
}

export function useIsAnonymous(): boolean {
	return useContext(AnonymousModeContext).isAnonymous;
}
