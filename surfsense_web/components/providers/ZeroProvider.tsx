"use client";

import { currentUserAtom } from "@/atoms/user/user-query.atoms";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";
import { ZeroProvider as ZeroReactProvider } from "@rocicorp/zero/react";
import { useAtomValue } from "jotai";

const cacheURL = process.env.NEXT_PUBLIC_ZERO_CACHE_URL || "http://localhost:4848";

export function ZeroProvider({ children }: { children: React.ReactNode }) {
	const { data: user } = useAtomValue(currentUserAtom);

	if (!user?.id) {
		return <>{children}</>;
	}

	const userID = String(user.id);
	const context = { userId: userID };

	return (
		<ZeroReactProvider {...{ userID, context, cacheURL, schema, queries }}>
			{children}
		</ZeroReactProvider>
	);
}
