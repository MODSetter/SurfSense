"use client";

import { useQuery } from "@rocicorp/zero/react";
import { useIsAnonymous } from "@/contexts/anonymous-mode";
import { queries } from "@/zero/queries";
import { PageUsageDisplay } from "./PageUsageDisplay";

export function AuthenticatedPageUsageDisplay() {
	const isAnonymous = useIsAnonymous();
	const [me] = useQuery(queries.user.me({}));

	if (isAnonymous || !me) return null;

	return <PageUsageDisplay pagesUsed={me.pagesUsed} pagesLimit={me.pagesLimit} />;
}
