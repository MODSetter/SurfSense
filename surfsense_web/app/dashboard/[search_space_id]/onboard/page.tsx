"use client";

import { useAtomValue } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import {
	globalLlmConfigStatusAtom,
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { Logo } from "@/components/Logo";
import { ModelProviderConnectionsPanel } from "@/components/settings/model-connections/model-provider-connections-panel";
import { Button } from "@/components/ui/button";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { getBearerToken, redirectToLogin } from "@/lib/auth-utils";
import { hasEnabledChatModel, isLlmOnboardingComplete } from "@/lib/onboarding";

export default function OnboardPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	const { data: globalConnections = [], isLoading: globalLoading } = useAtomValue(
		globalModelConnectionsAtom
	);
	const { data: connections = [] } = useAtomValue(modelConnectionsAtom);
	const { data: roles = {}, isLoading: rolesLoading } = useAtomValue(modelRolesAtom);
	const { data: globalConfigStatus, isLoading: globalConfigStatusLoading } =
		useAtomValue(globalLlmConfigStatusAtom);

	useEffect(() => {
		if (!getBearerToken()) redirectToLogin();
	}, []);

	const hasUsableChatModel = useMemo(
		() => hasEnabledChatModel([...globalConnections, ...connections]),
		[globalConnections, connections]
	);

	const onboardingComplete = isLlmOnboardingComplete(
		roles.chat_model_id,
		globalConnections,
		connections
	);

	const isLoading = globalLoading || rolesLoading || globalConfigStatusLoading;

	// Onboarding only applies when no global_llm_config.yaml exists. If a global
	// config is present (or onboarding is already complete), leave this page.
	const shouldLeaveOnboarding =
		!isLoading && (Boolean(globalConfigStatus?.exists) || onboardingComplete);

	useEffect(() => {
		if (shouldLeaveOnboarding) {
			router.replace(`/dashboard/${searchSpaceId}/new-chat`);
		}
	}, [shouldLeaveOnboarding, router, searchSpaceId]);

	useGlobalLoadingEffect(isLoading || shouldLeaveOnboarding);

	if (isLoading || shouldLeaveOnboarding) return null;

	return (
		<div className="flex min-h-screen select-none flex-col items-center justify-center bg-main-panel p-4">
			<div className="w-full max-w-3xl space-y-6 text-center">
				<Logo className="mx-auto h-12 w-12" />
				<div className="space-y-2">
					<h1 className="text-2xl font-semibold tracking-tight">Choose a model</h1>
					<p className="text-sm text-muted-foreground">
						Connect any supported provider, then enable the models you want SurfSense to use.
					</p>
				</div>
				<ModelProviderConnectionsPanel
					searchSpaceId={searchSpaceId}
					connections={connections}
					className="flex flex-col gap-6 text-left"
					footerAction={
						<Button
							className="min-w-[112px]"
							disabled={!onboardingComplete || !hasUsableChatModel}
							onClick={() => router.push(`/dashboard/${searchSpaceId}/new-chat`)}
						>
							Start
						</Button>
					}
					showAddProviderHeader={false}
				/>
			</div>
		</div>
	);
}
