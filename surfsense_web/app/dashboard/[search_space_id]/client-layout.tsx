"use client";

import { useAtomValue, useSetAtom } from "jotai";
import { Loader2 } from "lucide-react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { llmPreferencesAtom } from "@/atoms/llm-config/llm-config-query.atoms";
import { myAccessAtom } from "@/atoms/members/members-query.atoms";
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

	const { data: preferences = {}, isFetching: loading, error } = useAtomValue(llmPreferencesAtom);

	const isOnboardingComplete = useCallback(() => {
		return !!(
			preferences.long_context_llm_id &&
			preferences.fast_llm_id &&
			preferences.strategic_llm_id
		);
	}, [preferences]);

	const { data: access = null, isLoading: accessLoading } = useAtomValue(myAccessAtom);
	const [hasCheckedOnboarding, setHasCheckedOnboarding] = useState(false);

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

		// Wait for both preferences and access data to load
		if (!loading && !accessLoading && !hasCheckedOnboarding) {
			const onboardingComplete = isOnboardingComplete();

			// Only redirect to onboarding if user is the owner and onboarding is not complete
			// Invited members (non-owners) should skip onboarding and use existing config
			if (!onboardingComplete && isOwner) {
				router.push(`/dashboard/${searchSpaceId}/onboard`);
			}

			setHasCheckedOnboarding(true);
		}
	}, [
		loading,
		accessLoading,
		isOnboardingComplete,
		isOnboardingPage,
		isOwner,
		router,
		searchSpaceId,
		hasCheckedOnboarding,
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

	// Show loading screen while checking onboarding status (only on first load)
	if (!hasCheckedOnboarding && (loading || accessLoading) && !isOnboardingPage) {
		return (
			<div className="flex flex-col items-center justify-center min-h-screen space-y-4">
				<Card className="w-[350px] bg-background/60 backdrop-blur-sm">
					<CardHeader className="pb-2">
						<CardTitle className="text-xl font-medium">{t("loading_config")}</CardTitle>
						<CardDescription>{t("checking_llm_prefs")}</CardDescription>
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
			className="h-full bg-red-600 overflow-hidden"
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
					<header className="sticky top-0 z-50 flex h-16 shrink-0 items-center gap-2 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 border-b">
						<div className="flex items-center justify-between w-full gap-2 px-4">
							<div className="flex items-center gap-2">
								<SidebarTrigger className="-ml-1" />
								<Separator orientation="vertical" className="h-6" />
								<DashboardBreadcrumb />
							</div>
							<div className="flex items-center gap-2">
								<LanguageSwitcher />
							</div>
						</div>
					</header>
					<div className="grow flex-1 overflow-auto min-h-[calc(100vh-64px)]">{children}</div>
				</main>
			</SidebarInset>
		</SidebarProvider>
	);
}
