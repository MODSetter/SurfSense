"use client";

import type { ReactNode } from "react";
import { use } from "react";
import { FreeLayoutDataProvider } from "@/components/layout/providers/FreeLayoutDataProvider";
import { AnonymousModeProvider } from "@/contexts/anonymous-mode";
import { LoginGateProvider } from "@/contexts/login-gate";

interface FreeModelLayoutProps {
	children: ReactNode;
	params: Promise<{ model_slug: string }>;
}

export default function FreeModelLayout({ children, params }: FreeModelLayoutProps) {
	const { model_slug } = use(params);

	return (
		<AnonymousModeProvider initialModelSlug={model_slug}>
			<LoginGateProvider>
				<FreeLayoutDataProvider>{children}</FreeLayoutDataProvider>
			</LoginGateProvider>
		</AnonymousModeProvider>
	);
}
