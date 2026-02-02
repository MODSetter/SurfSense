"use client";

import {
	ArrowLeft,
	Bot,
	Brain,
	ChevronRight,
	FileText,
	Globe,
	type LucideIcon,
	Menu,
	MessageSquare,
	Settings,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { PublicChatSnapshotsManager } from "@/components/public-chat-snapshots/public-chat-snapshots-manager";
import { GeneralSettingsManager } from "@/components/settings/general-settings-manager";
import { LLMRoleManager } from "@/components/settings/llm-role-manager";
import { ModelConfigManager } from "@/components/settings/model-config-manager";
import { PromptConfigManager } from "@/components/settings/prompt-config-manager";
import { Button } from "@/components/ui/button";
import { trackSettingsViewed } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

interface SettingsNavItem {
	id: string;
	labelKey: string;
	descriptionKey: string;
	icon: LucideIcon;
}

const settingsNavItems: SettingsNavItem[] = [
	{
		id: "general",
		labelKey: "nav_general",
		descriptionKey: "nav_general_desc",
		icon: FileText,
	},
	{
		id: "models",
		labelKey: "nav_agent_configs",
		descriptionKey: "nav_agent_configs_desc",
		icon: Bot,
	},
	{
		id: "roles",
		labelKey: "nav_role_assignments",
		descriptionKey: "nav_role_assignments_desc",
		icon: Brain,
	},
	{
		id: "prompts",
		labelKey: "nav_system_instructions",
		descriptionKey: "nav_system_instructions_desc",
		icon: MessageSquare,
	},
	{
		id: "public-links",
		labelKey: "nav_public_links",
		descriptionKey: "nav_public_links_desc",
		icon: Globe,
	},
];

function SettingsSidebar({
	activeSection,
	onSectionChange,
	onBackToApp,
	isOpen,
	onClose,
}: {
	activeSection: string;
	onSectionChange: (section: string) => void;
	onBackToApp: () => void;
	isOpen: boolean;
	onClose: () => void;
}) {
	const t = useTranslations("searchSpaceSettings");

	const handleNavClick = (sectionId: string) => {
		onSectionChange(sectionId);
		onClose(); // Close sidebar on mobile after selection
	};

	return (
		<>
			{/* Mobile overlay */}
			<AnimatePresence>
				{isOpen && (
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
						onClick={onClose}
					/>
				)}
			</AnimatePresence>

			{/* Sidebar */}
			<aside
				className={cn(
					"fixed md:relative left-0 top-0 z-50 md:z-auto",
					"w-72 shrink-0 bg-background md:bg-muted/30 h-full flex flex-col",
					"md:border-r",
					"transition-transform duration-300 ease-out",
					"md:translate-x-0",
					isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
				)}
			>
				{/* Header with title */}
				<div className="p-4 space-y-3">
					<div className="flex items-center justify-between">
						<Button
							variant="ghost"
							onClick={onBackToApp}
							className="justify-start gap-3 h-11 px-3 hover:bg-muted group"
						>
							<div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
								<ArrowLeft className="h-4 w-4 text-primary" />
							</div>
							<span className="font-medium">{t("back_to_app")}</span>
						</Button>
						{/* Mobile close button */}
						<Button variant="ghost" size="icon" onClick={onClose} className="md:hidden h-9 w-9">
							<X className="h-5 w-5" />
						</Button>
					</div>
					{/* Settings Title */}
					<div className="px-3">
						<h2 className="text-lg font-semibold text-foreground">{t("title")}</h2>
					</div>
				</div>

				{/* Navigation Items */}
				<nav className="flex-1 px-3 py-2 space-y-1 overflow-y-auto">
					{settingsNavItems.map((item, index) => {
						const isActive = activeSection === item.id;
						const Icon = item.icon;

						return (
							<motion.button
								key={item.id}
								initial={{ opacity: 0, x: -10 }}
								animate={{ opacity: 1, x: 0 }}
								transition={{ delay: 0.1 + index * 0.05, duration: 0.3 }}
								onClick={() => handleNavClick(item.id)}
								whileHover={{ scale: 1.01 }}
								whileTap={{ scale: 0.99 }}
								className={cn(
									"relative w-full flex items-center gap-3 px-3 py-3 rounded-xl text-left transition-all duration-200",
									isActive ? "bg-muted shadow-sm border border-border" : "hover:bg-muted/60"
								)}
							>
								{isActive && (
									<motion.div
										layoutId="settingsActiveIndicator"
										className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-r-full"
										initial={false}
										transition={{
											type: "spring",
											stiffness: 500,
											damping: 35,
										}}
									/>
								)}
								<div
									className={cn(
										"flex items-center justify-center w-9 h-9 rounded-lg transition-colors",
										isActive ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
									)}
								>
									<Icon className="h-4 w-4" />
								</div>
								<div className="flex-1 min-w-0">
									<p
										className={cn(
											"text-sm font-medium truncate transition-colors",
											isActive ? "text-foreground" : "text-muted-foreground"
										)}
									>
										{t(item.labelKey)}
									</p>
									<p className="text-xs text-muted-foreground/70 truncate">
										{t(item.descriptionKey)}
									</p>
								</div>
								<ChevronRight
									className={cn(
										"h-4 w-4 shrink-0 transition-all",
										isActive
											? "text-primary opacity-100 translate-x-0"
											: "text-muted-foreground/40 opacity-0 -translate-x-1"
									)}
								/>
							</motion.button>
						);
					})}
				</nav>
			</aside>
		</>
	);
}

function SettingsContent({
	activeSection,
	searchSpaceId,
	onMenuClick,
}: {
	activeSection: string;
	searchSpaceId: number;
	onMenuClick: () => void;
}) {
	const t = useTranslations("searchSpaceSettings");
	const activeItem = settingsNavItems.find((item) => item.id === activeSection);
	const Icon = activeItem?.icon || Settings;

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ delay: 0.2, duration: 0.4 }}
			className="flex-1 min-w-0 h-full overflow-hidden bg-background"
		>
			<div className="h-full overflow-y-auto">
				<div className="max-w-4xl mx-auto p-4 md:p-6 lg:p-10">
					{/* Section Header */}
					<AnimatePresence mode="wait">
						<motion.div
							key={activeSection + "-header"}
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -10 }}
							transition={{ duration: 0.3 }}
							className="mb-6 md:mb-8"
						>
							<div className="flex items-center gap-3 md:gap-4">
								{/* Mobile menu button */}
								<Button
									variant="outline"
									size="icon"
									onClick={onMenuClick}
									className="md:hidden h-10 w-10 shrink-0"
								>
									<Menu className="h-5 w-5" />
								</Button>
								<motion.div
									initial={{ scale: 0.8, opacity: 0 }}
									animate={{ scale: 1, opacity: 1 }}
									transition={{ delay: 0.1, duration: 0.3 }}
									className="flex items-center justify-center w-10 h-10 md:w-14 md:h-14 rounded-lg md:rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 border border-primary/10 shadow-sm shrink-0"
								>
									<Icon className="h-5 w-5 md:h-7 md:w-7 text-primary" />
								</motion.div>
								<div className="min-w-0">
									<h1 className="text-lg md:text-2xl font-bold tracking-tight truncate">
										{activeItem ? t(activeItem.labelKey) : ""}
									</h1>
								</div>
							</div>
						</motion.div>
					</AnimatePresence>

					{/* Section Content */}
					<AnimatePresence mode="wait">
						<motion.div
							key={activeSection}
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -20 }}
							transition={{
								duration: 0.35,
								ease: [0.4, 0, 0.2, 1],
							}}
						>
							{activeSection === "general" && (
								<GeneralSettingsManager searchSpaceId={searchSpaceId} />
							)}
							{activeSection === "models" && <ModelConfigManager searchSpaceId={searchSpaceId} />}
							{activeSection === "roles" && <LLMRoleManager searchSpaceId={searchSpaceId} />}
							{activeSection === "prompts" && <PromptConfigManager searchSpaceId={searchSpaceId} />}
							{activeSection === "public-links" && (
								<PublicChatSnapshotsManager searchSpaceId={searchSpaceId} />
							)}
						</motion.div>
					</AnimatePresence>
				</div>
			</div>
		</motion.div>
	);
}

export default function SettingsPage() {
	const router = useRouter();
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);
	const [activeSection, setActiveSection] = useState("general");
	const [isSidebarOpen, setIsSidebarOpen] = useState(false);

	// Track settings section view
	useEffect(() => {
		trackSettingsViewed(searchSpaceId, activeSection);
	}, [searchSpaceId, activeSection]);

	const handleBackToApp = useCallback(() => {
		router.push(`/dashboard/${searchSpaceId}/new-chat`);
	}, [router, searchSpaceId]);

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.3 }}
			className="fixed inset-0 z-50 flex bg-muted/40"
		>
			<div className="flex h-full w-full p-0 md:p-2">
				<div className="flex h-full w-full overflow-hidden bg-background md:rounded-xl md:border md:shadow-sm">
					<SettingsSidebar
						activeSection={activeSection}
						onSectionChange={setActiveSection}
						onBackToApp={handleBackToApp}
						isOpen={isSidebarOpen}
						onClose={() => setIsSidebarOpen(false)}
					/>
					<SettingsContent
						activeSection={activeSection}
						searchSpaceId={searchSpaceId}
						onMenuClick={() => setIsSidebarOpen(true)}
					/>
				</div>
			</div>
		</motion.div>
	);
}
