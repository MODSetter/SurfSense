"use client";

import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";
import { ZeroProvider as ZeroReactProvider } from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";

const cacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848";

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const { data: user } = useAtomValue(currentUserAtom);
	const userID = user?.id ? String(user.id) : "";
	const context = user?.id ? { userId: String(user.id) } : undefined;

	return (
		<ZeroReactProvider {...{ userID, context, cacheURL, schema, queries }}>
			{children}
		</ZeroReactProvider>
	);
}
