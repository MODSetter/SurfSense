"use client";

import { Suspense } from "react";
import TokenHandler from "@/components/TokenHandler";

export default function AuthCallbackPage() {
	// Suspense fallback returns null - the GlobalLoadingProvider handles the loading UI
	// TokenHandler uses useGlobalLoadingEffect to show the loading screen
	return (
		<Suspense fallback={null}>
			<TokenHandler
				redirectPath="/dashboard"
				tokenParamName="token"
				storageKey="surfsense_bearer_token"
			/>
		</Suspense>
	);
}
