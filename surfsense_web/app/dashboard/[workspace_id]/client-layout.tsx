"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useEffect } from "react";
import { pendingUserImageDataUrlsAtom } from "@/atoms/chat/pending-user-images.atom";
import { llmSetupStatusAtomFamily } from "@/atoms/model-connections/model-connections-query.atoms";
import { activeWorkspaceIdAtom } from "@/atoms/workspaces/workspace-query.atoms";
import { ConnectorIndicator } from "@/components/assistant-ui/connector-popup";
import { DocumentUploadDialogProvider } from "@/components/assistant-ui/document-upload-popup";
import { LayoutDataProvider } from "@/components/layout";
import { OnboardingTour } from "@/components/onboarding-tour";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useFolderSync } from "@/hooks/use-folder-sync";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { useElectronAPI } from "@/hooks/use-platform";

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

	// Single source of truth for the onboarding gate. Keyed by the route
	// workspaceId so the verdict can never lag behind a workspace switch.
	const {
		data: setupStatus,
		isLoading: setupLoading,
		error: setupError,
	} = useAtomValue(llmSetupStatusAtomFamily(Number(workspaceId)));

	const isOnboardingPage = pathname?.includes("/onboard");
	const isWorkspaceReady = activeWorkspaceId === workspaceId;

	const needsSetup = setupStatus?.status === "needs_setup";
	const isReady = setupStatus?.status === "ready";
	const canConfigure = setupStatus?.can_configure ?? false;

	// Redirect into onboarding (configurable members) or out of it (workspace
	// became ready). Both directions live here; the pages themselves are dumb.
	useEffect(() => {
		if (setupLoading || setupError) return;
		if (needsSetup && canConfigure && !isOnboardingPage) {
			router.replace(`/dashboard/${workspaceId}/onboard`);
		} else if (isReady && isOnboardingPage) {
			router.replace(`/dashboard/${workspaceId}/new-chat`);
		}
	}, [
		setupLoading,
		setupError,
		needsSetup,
		canConfigure,
		isReady,
		isOnboardingPage,
		router,
		workspaceId,
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
		if (electronAPI?.getActiveWorkspace && electronAPI.setActiveWorkspace) {
			const setActiveWorkspace = electronAPI.setActiveWorkspace;
			electronAPI
				.getActiveWorkspace()
				.then((stored: string | null) => {
					if (!stored) {
						setActiveWorkspace(activeSeacrhSpaceId);
					}
				})
				.catch(() => {});
		}
	}, [workspace_id, setActiveWorkspaceIdState, electronAPI]);

	// Currently navigating between onboarding and the dashboard.
	const isRedirecting =
		!setupLoading &&
		!setupError &&
		((needsSetup && canConfigure && !isOnboardingPage) || (isReady && isOnboardingPage));

	// Block children until the workspace is synced and the setup verdict is in,
	// so an unconfigured workspace never flashes the composer.
	const shouldShowLoading = !setupError && (!isWorkspaceReady || setupLoading || isRedirecting);

	useGlobalLoadingEffect(shouldShowLoading);

	// Wire desktop app file watcher -> single-file re-index API
	useFolderSync();

	if (shouldShowLoading) {
		return null;
	}

	if (setupError) {
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
							{setupError instanceof Error ? setupError.message : String(setupError)}
						</p>
					</CardContent>
				</Card>
			</div>
		);
	}

	// Member without permission to connect a model in an unconfigured workspace.
	if (needsSetup && !canConfigure) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen p-4">
				<Card className="w-[440px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">No model available</CardTitle>
						<CardDescription>
							A workspace admin needs to connect a language model before chat is available
							here.
						</CardDescription>
					</CardHeader>
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
			<LayoutDataProvider workspaceId={workspaceId}>
				{children}
				<ConnectorIndicator showTrigger={false} />
			</LayoutDataProvider>
		</DocumentUploadDialogProvider>
	);
}
