"use client";

import { FreeLayoutDataProvider } from "@/components/layout/providers/FreeLayoutDataProvider";
import { AnonymousModeProvider } from "@/contexts/anonymous-mode";
import { LoginGateProvider } from "@/contexts/login-gate";
import { FreeChatPage } from "./free-chat-page";

export function FreeChatApp({ modelSlug }: { modelSlug: string }) {
	return (
		<AnonymousModeProvider key={modelSlug} initialModelSlug={modelSlug}>
			<LoginGateProvider>
				<FreeLayoutDataProvider>
					<FreeChatPage />
				</FreeLayoutDataProvider>
			</LoginGateProvider>
		</AnonymousModeProvider>
	);
}
