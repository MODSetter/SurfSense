"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { DocumentUploadDialogProvider } from "@/components/assistant-ui/document-upload-popup";
import { DashboardBreadcrumb } from "@/components/dashboard-breadcrumb";
import { LayoutDataProvider } from "@/components/layout";
import { OnboardingTour } from "@/components/onboarding-tour";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";

export function DashboardClientLayout({
	children,
	searchSpaceId,
}: {
	children: React.ReactNode;
	searchSpaceId: string;
	navSecondary?: any[];
	navMain?: any[];
}) {
	const t = useTranslations("dashboard");
	const router = useRouter();
	const pathname = usePathname();
	const { search_space_id } = useParams();
	const setActiveSearchSpaceIdState = useSetAtom(activeSearchSpaceIdAtom);

	const {
		data: preferences = {},
		isFetching: loading,
		error,
		refetch: refetchPreferences,
	} = useAtomValue(llmPreferencesAtom);
	const { data: globalConfigs = [], isFetching: globalConfigsLoading } =
		useAtomValue(globalNewLLMConfigsAtom);
	const { mutateAsync: updatePreferences } = useAtomValue(updateLLMPreferencesMutationAtom);

	const isOnboardingComplete = useCallback(() => {
		// Check that both LLM IDs are set (including 0 for Auto mode)
		return (
			preferences.agent_llm_id !== null &&
			preferences.agent_llm_id !== undefined &&
			preferences.document_summary_llm_id !== null &&
			preferences.document_summary_llm_id !== undefined
		);
	}, [preferences]);

	const { data: access = null, isLoading: accessLoading } = useAtomValue(myAccessAtom);
	const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false);
	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const hasAttemptedAutoConfig = useRef(false);

	const isOnboardingPage = pathname?.includes("/onboard");
	const isOwner = access?.is_owner ?? false;

	useEffect(() => {
		if (isOnboardingPage) {
			setHasCheckedOnboarding(true);
			return;
		}

		if (
			!loading &&
			!accessLoading &&
			!globalConfigsLoading &&
			!hasCheckedOnboarding &&
			!isAutoConfiguring
		) {
			const onboardingComplete = isOnboardingComplete();

			if (onboardingComplete) {
				setHasCheckedOnboarding(true);
				return;
			}

			if (!isOwner) {
				setHasCheckedOnboarding(true);
				return;
			}

			if (globalConfigs.length > 0 && !hasAttemptedAutoConfig.current) {
				hasAttemptedAutoConfig.current = true;
				setIsAutoConfiguring(true);

				const autoConfigureWithGlobal = async () => {
					try {
						const firstGlobalConfig = globalConfigs[0];
						await updatePreferences({
							search_space_id: Number(searchSpaceId),
							data: {
								agent_llm_id: firstGlobalConfig.id,
								document_summary_llm_id: firstGlobalConfig.id,
							},
						});

						await refetchPreferences();

						toast.success("AI configured automatically!", {
							description: `Using ${firstGlobalConfig.name}. Customize in Settings.`,
						});

						setHasCheckedOnboarding(true);
					} catch (error) {
						console.error("Auto-configuration failed:", error);
						router.push(`/dashboard/${searchSpaceId}/onboard`);
					} finally {
						setIsAutoConfiguring(false);
					}
				};

				autoConfigureWithGlobal();
				return;
			}

			router.push(`/dashboard/${searchSpaceId}/onboard`);
			setHasCheckedOnboarding(true);
		}
	}, [
		loading,
		accessLoading,
		globalConfigsLoading,
		isOnboardingComplete,
		isOnboardingPage,
		isOwner,
		isAutoConfiguring,
		globalConfigs,
		router,
		searchSpaceId,
		hasCheckedOnboarding,
		updatePreferences,
		refetchPreferences,
	]);

	useEffect(() => {
		const activeSeacrhSpaceId =
			typeof search_space_id === "string"
				? search_space_id
				: Array.isArray(search_space_id) && search_space_id.length > 0
					? search_space_id[0]
					: "";
		if (!activeSeacrhSpaceId) return;
		setActiveSearchSpaceIdState(activeSeacrhSpaceId);
	}, [search_space_id, setActiveSearchSpaceIdState]);

	// Determine if we should show loading
	const shouldShowLoading =
		(!hasCheckedOnboarding &&
			(loading || accessLoading || globalConfigsLoading) &&
			!isOnboardingPage) ||
		isAutoConfiguring;

	// Use global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(shouldShowLoading);

	if (shouldShowLoading) {
		return null;
	}

	if (error && !hasCheckedOnboarding && !isOnboardingPage) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[400px] bg-background/60 backdrop-blur-sm border-destructive/20">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium text-destructive">
							{t("config_error")}
						</CardTitle>
						<CardDescription>{t("failed_load_llm_config")}</CardDescription>
					</CardHeader>
					<CardContent>
						<p className="text-sm text-muted-foreground">
							{error instanceof Error ? error.message : String(error)}
						</p>
					</CardContent>
				</Card>
			</div>
		);
	}

	return (
		<DocumentUploadDialogProvider>
			<OnboardingTour />
			<LayoutDataProvider searchSpaceId={searchSpaceId} breadcrumb={<DashboardBreadcrumb />}>
				{children}
			</LayoutDataProvider>
		</DocumentUploadDialogProvider>
	);
}
