"use client";

import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { Loader2, PanelRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useParams, usePathname, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import type React from "react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { activeChathatUIAtom, activeChatIdAtom } from "@/atoms/chats/ui.atoms";
import { llmPreferencesAtom } from "@/atoms/llm-config/llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/seach-spaces/seach-space-queries.atom";
import { ChatPanelContainer } from "@/components/chat/ChatPanel/ChatPanelContainer";
import { DashboardBreadcrumb } from "@/components/dashboard-breadcrumb";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { AppSidebarProvider } from "@/components/sidebar/AppSidebarProvider";
import { ThemeTogglerComponent } from "@/components/theme/theme-toggle";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";
import { useUserAccess } from "@/hooks/use-rbac";
import { cn } from "@/lib/utils";

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
	const searchSpaceIdNum = Number(searchSpaceId);
	const { search_space_id, chat_id } = useParams();
	const [chatUIState, setChatUIState] = useAtom(activeChathatUIAtom);
	const activeChatId = useAtomValue(activeChatIdAtom);
	const setActiveSearchSpaceIdState = useSetAtom(activeSearchSpaceIdAtom);
	const setActiveChatIdState = useSetAtom(activeChatIdAtom);
	const [showIndicator, setShowIndicator] = useState(false);

	const { isChatPannelOpen } = chatUIState;

	// Check if we're on the researcher page
	const isResearcherPage = pathname?.includes("/researcher");

	// Show indicator when chat becomes active and panel is closed
	useEffect(() => {
		if (activeChatId && !isChatPannelOpen) {
			setShowIndicator(true);
			// Hide indicator after 5 seconds
			const timer = setTimeout(() => setShowIndicator(false), 5000);
			return () => clearTimeout(timer);
		} else {
			setShowIndicator(false);
		}
	}, [activeChatId, isChatPannelOpen]);

	const { data: preferences = {}, isFetching: loading, error } = useAtomValue(llmPreferencesAtom);

	const isOnboardingComplete = useCallback(() => {
		return !!(
			preferences.long_context_llm_id &&
			preferences.fast_llm_id &&
			preferences.strategic_llm_id
		);
	}, [preferences]);

	const { access, loading: accessLoading } = useUserAccess(searchSpaceIdNum);
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
	}, [search_space_id]);

	useEffect(() => {
		const activeChatId =
			typeof chat_id === "string"
				? chat_id
				: Array.isArray(chat_id) && chat_id.length > 0
					? chat_id[0]
					: "";
		if (!activeChatId) return;
		setActiveChatIdState(activeChatId);
	}, [chat_id, search_space_id]);

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
						<p className="text-sm text-muted-foreground">{error.message}</p>
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
				<main className="flex h-full">
					<div className="flex grow flex-col h-full border-r">
						<header className="sticky top-0 z-50 flex h-16 shrink-0 items-center gap-2 bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 border-b">
							<div className="flex items-center justify-between w-full gap-2 px-4">
								<div className="flex items-center gap-2">
									<SidebarTrigger className="-ml-1" />
									<Separator orientation="vertical" className="h-6" />
									<DashboardBreadcrumb />
								</div>
								<div className="flex items-center gap-2">
									<LanguageSwitcher />
									<ThemeTogglerComponent />
									{/* Only show artifacts toggle on researcher page */}
									{isResearcherPage && (
										<motion.div
											className="relative"
											animate={
												showIndicator
													? {
															scale: [1, 1.05, 1],
														}
													: {}
											}
											transition={{
												duration: 2,
												repeat: showIndicator ? Number.POSITIVE_INFINITY : 0,
												ease: "easeInOut",
											}}
										>
											<motion.button
												type="button"
												onClick={() => {
													setChatUIState((prev) => ({
														...prev,
														isChatPannelOpen: !isChatPannelOpen,
													}));
													setShowIndicator(false);
												}}
												className={cn(
													"shrink-0 rounded-full p-2 transition-all duration-300 relative",
													showIndicator
														? "bg-primary/20 hover:bg-primary/30 shadow-lg shadow-primary/25"
														: "hover:bg-muted",
													activeChatId && !showIndicator && "hover:bg-primary/10"
												)}
												title="Toggle Artifacts Panel"
												whileHover={{ scale: 1.05 }}
												whileTap={{ scale: 0.95 }}
											>
												<motion.div
													animate={
														showIndicator
															? {
																	rotate: [0, -10, 10, -10, 0],
																}
															: {}
													}
													transition={{
														duration: 0.5,
														repeat: showIndicator ? Number.POSITIVE_INFINITY : 0,
														repeatDelay: 2,
													}}
												>
													<PanelRight
														className={cn(
															"h-4 w-4 transition-colors",
															showIndicator && "text-primary"
														)}
													/>
												</motion.div>
											</motion.button>

											{/* Pulsing indicator badge */}
											<AnimatePresence>
												{showIndicator && (
													<motion.div
														initial={{ opacity: 0, scale: 0 }}
														animate={{ opacity: 1, scale: 1 }}
														exit={{ opacity: 0, scale: 0 }}
														className="absolute -right-1 -top-1 pointer-events-none"
													>
														<motion.div
															animate={{
																scale: [1, 1.3, 1],
															}}
															transition={{
																duration: 1.5,
																repeat: Number.POSITIVE_INFINITY,
																ease: "easeInOut",
															}}
															className="relative"
														>
															<div className="h-2.5 w-2.5 rounded-full bg-primary shadow-lg" />
															<motion.div
																animate={{
																	scale: [1, 2.5, 1],
																	opacity: [0.6, 0, 0.6],
																}}
																transition={{
																	duration: 1.5,
																	repeat: Number.POSITIVE_INFINITY,
																	ease: "easeInOut",
																}}
																className="absolute inset-0 h-2.5 w-2.5 rounded-full bg-primary"
															/>
														</motion.div>
													</motion.div>
												)}
											</AnimatePresence>
										</motion.div>
									)}
								</div>
							</div>
						</header>
						<div className="grow flex-1 overflow-auto min-h-[calc(100vh-64px)]">{children}</div>
					</div>
					{/* Only render chat panel on researcher page */}
					{isResearcherPage && <ChatPanelContainer />}
				</main>
			</SidebarInset>
		</SidebarProvider>
	);
}
