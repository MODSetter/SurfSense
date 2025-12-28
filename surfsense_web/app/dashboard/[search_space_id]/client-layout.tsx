"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Loader2 } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
import { updateLLMPreferencesMutationAtom } from "@/atoms/new-llm-config/new-llm-config-mutation.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { DashboardBreadcrumb } from "@/components/dashboard-breadcrumb";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { AppSidebarProvider } from "@/components/sidebar/AppSidebarProvider";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export function DashboardClientLayout({
	children,
	searchSpaceId,
	navSecondary,
	navMain,
}: {
	children: React.ReactNode;
	searchSpaceId: string;
	navSecondary: any[];
	navMain: any[];
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
		return !!(preferences.agent_llm_id && preferences.document_summary_llm_id);
	}, [preferences]);

	const { data: access = null, isLoading: accessLoading } = useAtomValue(myAccessAtom);
	const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false);
	const [isAutoConfiguring, setIsAutoConfiguring] = useState(false);
	const hasAttemptedAutoConfig = useRef(false);

	// Skip onboarding check if we're already on the onboarding page
	const isOnboardingPage = pathname?.includes("/onboard");

	// Only owners should see onboarding - invited members use existing config
	const isOwner = access?.is_owner ?? false;

	// Translate navigation items
	const tNavMenu = useTranslations("nav_menu");
	const translatedNavMain = useMemo(() => {
		return navMain.map((item) => ({
			...item,
			title: tNavMenu(item.title.toLowerCase().replace(/ /g, "_")),
			items: item.items?.map((subItem: any) => ({
				...subItem,
				title: tNavMenu(subItem.title.toLowerCase().replace(/ /g, "_")),
			})),
		}));
	}, [navMain, tNavMenu]);

	const translatedNavSecondary = useMemo(() => {
		return navSecondary.map((item) => ({
			...item,
			title: item.title === "All Search Spaces" ? tNavMenu("all_search_spaces") : item.title,
		}));
	}, [navSecondary, tNavMenu]);

	const [open, setOpen] = useState<boolean>(() => {
		try {
			const match = document.cookie.match(/(?:^|; )sidebar_state=([^;]+)/);
			if (match) return match[1] === "true";
		} catch {
			// ignore
		}
		return true;
	});

	useEffect(() => {
		// Skip check if already on onboarding page
		if (isOnboardingPage) {
			setHasCheckedOnboarding(true);
			return;
		}

		// Wait for all data to load
		if (
			!loading &&
			!accessLoading &&
			!globalConfigsLoading &&
			!hasCheckedOnboarding &&
			!isAutoConfiguring
		) {
			const onboardingComplete = isOnboardingComplete();

			// If onboarding is complete, nothing to do
			if (onboardingComplete) {
				setHasCheckedOnboarding(true);
				return;
			}

			// Only handle onboarding for owners
			if (!isOwner) {
				setHasCheckedOnboarding(true);
				return;
			}

			// If global configs available, auto-configure without going to onboard page
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
						// Fall back to onboard page
						router.push(`/dashboard/${searchSpaceId}/onboard`);
					} finally {
						setIsAutoConfiguring(false);
					}
				};

				autoConfigureWithGlobal();
				return;
			}

			// No global configs - redirect to onboard page
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

	// Synchronize active search space and chat IDs with URL
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

	// Show loading screen while checking onboarding status or auto-configuring
	if (
		(!hasCheckedOnboarding &&
			(loading || accessLoading || globalConfigsLoading) &&
			!isOnboardingPage) ||
		isAutoConfiguring
	) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">
							{isAutoConfiguring ? "Setting up AI..." : t("loading_config")}
						</CardTitle>
						<CardDescription>
							{isAutoConfiguring
								? "Auto-configuring with available settings"
								: t("checking_llm_prefs")}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex justify-center py-6">
						<Loader2 className="h-12 w-12 text-primary animate-spin" />
					</CardContent>
				</Card>
			</div>
		);
	}

	// Show error screen if there's an error loading preferences (but not on onboarding page)
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
		<SidebarProvider
			className="h-full overflow-hidden"
			open={open}
			onOpenChange={setOpen}
		>
			{/* Use AppSidebarProvider which fetches user, search space, and recent chats */}
			<AppSidebarProvider
				searchSpaceId={searchSpaceId}
				navSecondary={translatedNavSecondary}
				navMain={translatedNavMain}
			/>
			<SidebarInset className="h-full ">
				<main className="flex flex-col h-full">
					<header className="sticky top-0 flex h-16 shrink-0 items-center gap-2 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 border-b">
						<div className="flex items-center justify-between w-full gap-2 px-4">
							<div className="flex items-center gap-2">
								<SidebarTrigger className="-ml-1" />
								<div className="hidden md:flex items-center gap-2">
									<Separator orientation="vertical" className="h-6" />
									<DashboardBreadcrumb />
								</div>
							</div>
							<div className="flex items-center gap-2">
								<LanguageSwitcher />
							</div>
						</div>
					</header>
					<div className="flex-1 overflow-hidden">{children}</div>
				</main>
			</SidebarInset>
		</SidebarProvider>
	);
}
