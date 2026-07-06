"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useEffect, useState } from "react";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import {
	globalLlmConfigStatusAtom,
	globalModelConnectionsAtom,
	modelConnectionsAtom,
	modelRolesAtom,
} from "@/atoms/model-connections/model-connections-query.atoms";
import { activeWorkspaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { DocumentUploadDialogProvider } from "@/components/assistant-ui/document-upload-popup";
import { LayoutDataProvider } from "@/components/layout";
import { OnboardingTour } from "@/components/onboarding-tour";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useFolderSync } from "@/hooks/use-folder-sync";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { useElectronAPI } from "@/hooks/use-platform";
import { isLlmOnboardingComplete } from "@/lib/onboarding";

export function DashboardClientLayout({
	children,
	workspaceId,
}: {
	children: React.ReactNode;
	workspaceId: string;
}) {
	const t = useTranslations("dashboard");
	const router = useRouter();
	const pathname = usePathname();
	const { workspace_id } = useParams();
	const activeWorkspaceId = useAtomValue(activeWorkspaceIdAtom);
	const setActiveWorkspaceIdState = useSetAtom(activeWorkspaceIdAtom);
	const setPendingUserImageUrls = useSetAtom(pendingUserImageDataUrlsAtom);

	const { data: modelRoles = {}, isLoading: loading, error } = useAtomValue(modelRolesAtom);
	const { data: globalConnections = [], isLoading: globalConfigsLoading } = useAtomValue(
		globalModelConnectionsAtom
	);
	const { data: modelConnections = [], isLoading: modelConnectionsLoading } =
		useAtomValue(modelConnectionsAtom);
	const { data: globalConfigStatus, isLoading: globalConfigStatusLoading } =
		useAtomValue(globalLlmConfigStatusAtom);

	const { data: access = null, isLoading: accessLoading } = useAtomValue(myAccessAtom);
	const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false);

	const isOnboardingPage = pathname?.includes("/onboard");
	const isOwner = access?.is_owner ?? false;
	const isSearchSpaceReady = activeWorkspaceId === workspaceId;

	useEffect(() => {
		if (isSearchSpaceReady) return;
		setHasCheckedOnboarding(false);
	}, [isSearchSpaceReady]);

	useEffect(() => {
		if (isOnboardingPage) {
			setHasCheckedOnboarding(true);
			return;
		}

		if (
			isSearchSpaceReady &&
			!loading &&
			!accessLoading &&
			!globalConfigsLoading &&
			!globalConfigStatusLoading &&
			!modelConnectionsLoading &&
			!hasCheckedOnboarding
		) {
			// Onboarding is only relevant when no operator-provided
			// global_llm_config.yaml exists. When it does, search spaces inherit
			// the global config and should never be forced into onboarding.
			if (globalConfigStatus?.exists) {
				setHasCheckedOnboarding(true);
				return;
			}

			const onboardingComplete = isLlmOnboardingComplete(
				modelRoles.chat_model_id,
				globalConnections,
				modelConnections
			);

			if (onboardingComplete) {
				setHasCheckedOnboarding(true);
				return;
			}

			if (!isOwner) {
				setHasCheckedOnboarding(true);
				return;
			}

			router.push(`/dashboard/${workspaceId}/onboard`);
			setHasCheckedOnboarding(true);
		}
	}, [
		isSearchSpaceReady,
		loading,
		accessLoading,
		globalConfigsLoading,
		globalConfigStatusLoading,
		globalConfigStatus,
		modelConnectionsLoading,
		modelRoles.chat_model_id,
		globalConnections,
		modelConnections,
		isOnboardingPage,
		isOwner,
		router,
		workspaceId,
		hasCheckedOnboarding,
	]);

	const electronAPI = useElectronAPI();

	useEffect(() => {
		const htmlBackground = document.documentElement.style.backgroundColor;
		const bodyBackground = document.body.style.backgroundColor;

		document.documentElement.style.backgroundColor = "var(--panel)";
		document.body.style.backgroundColor = "var(--panel)";

		return () => {
			document.documentElement.style.backgroundColor = htmlBackground;
			document.body.style.backgroundColor = bodyBackground;
		};
	}, []);

	useEffect(() => {
		if (!electronAPI?.onChatScreenCapture) return;
		return electronAPI.onChatScreenCapture((dataUrl: string) => {
			if (typeof dataUrl !== "string" || !dataUrl.startsWith("data:image/")) return;
			setPendingUserImageUrls((prev) => [...prev, dataUrl]);
		});
	}, [electronAPI, setPendingUserImageUrls]);

	useEffect(() => {
		const activeSeacrhSpaceId =
			typeof workspace_id === "string"
				? workspace_id
				: Array.isArray(workspace_id) && workspace_id.length > 0
					? workspace_id[0]
					: "";
		if (!activeSeacrhSpaceId) return;
		setActiveWorkspaceIdState(activeSeacrhSpaceId);

		// Sync to Electron store if stored value is null (first navigation)
		if (electronAPI?.getActiveSearchSpace && electronAPI.setActiveSearchSpace) {
			const setActiveSearchSpace = electronAPI.setActiveSearchSpace;
			electronAPI
				.getActiveSearchSpace()
				.then((stored: string | null) => {
					if (!stored) {
						setActiveSearchSpace(activeSeacrhSpaceId);
					}
				})
				.catch(() => {});
		}
	}, [workspace_id, setActiveWorkspaceIdState, electronAPI]);

	// Determine if we should show loading
	const shouldShowLoading =
		!hasCheckedOnboarding &&
		(!isSearchSpaceReady ||
			loading ||
			accessLoading ||
			globalConfigsLoading ||
			globalConfigStatusLoading ||
			modelConnectionsLoading) &&
		!isOnboardingPage;

	// Use global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(shouldShowLoading);

	// Wire desktop app file watcher -> single-file re-index API
	useFolderSync();

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

	if (isOnboardingPage) {
		return <>{children}</>;
	}

	return (
		<DocumentUploadDialogProvider>
			<OnboardingTour />
			<LayoutDataProvider searchSpaceId={workspaceId}>{children}</LayoutDataProvider>
		</DocumentUploadDialogProvider>
	);
}
