"use client";

import Link from "next/link";
import { createContext, type ReactNode, useCallback, useContext, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { useIsAnonymous } from "./anonymous-mode";

interface LoginGateContextValue {
	gate: (feature: string) => void;
}

const LoginGateContext = createContext<LoginGateContextValue>({
	gate: () => {},
});

export function LoginGateProvider({ children }: { children: ReactNode }) {
	const isAnonymous = useIsAnonymous();
	const [feature, setFeature] = useState<string | null>(null);

	const gate = useCallback(
		(feat: string) => {
			if (isAnonymous) {
				setFeature(feat);
			}
		},
		[isAnonymous]
	);

	const close = () => setFeature(null);

	return (
		<LoginGateContext.Provider value={{ gate }}>
			{children}
			<Dialog open={feature !== null} onOpenChange={(open) => !open && close()}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>Create a free account to {feature}</DialogTitle>
						<DialogDescription>
							Get $5 of premium credit, save chat history, upload documents, use all AI tools,
							and connect 30+ integrations.
						</DialogDescription>
					</DialogHeader>
					<DialogFooter className="flex flex-col gap-2 sm:flex-row">
						<Button asChild>
							<Link href="/register">Create Free Account</Link>
						</Button>
						<Button variant="outline" asChild>
							<Link href="/login">Log In</Link>
						</Button>
					</DialogFooter>
				</DialogContent>
			</Dialog>
		</LoginGateContext.Provider>
	);
}

export function useLoginGate(): LoginGateContextValue {
	return useContext(LoginGateContext);
}

/**
 * Returns a click handler that triggers the login gate when anonymous,
 * or calls the original handler when authenticated.
 */
export function useGatedHandler(handler: (() => void) | undefined, feature: string): () => void {
	const { gate } = useLoginGate();
	const isAnonymous = useIsAnonymous();

	return useCallback(() => {
		if (isAnonymous) {
			gate(feature);
		} else {
			handler?.();
		}
	}, [isAnonymous, gate, feature, handler]);
}
