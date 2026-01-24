"use client";

import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { UnifiedLoadingScreen } from "@/components/ui/unified-loading-screen";
import TokenHandler from "@/components/TokenHandler";

export default function AuthCallbackPage() {
	const t = useTranslations("auth");
	
	return (
		<Suspense fallback={<UnifiedLoadingScreen variant="default" message={t("processing_authentication")} />}>
			<TokenHandler
				redirectPath="/dashboard"
				tokenParamName="token"
				storageKey="surfsense_bearer_token"
			/>
		</Suspense>
	);
}
