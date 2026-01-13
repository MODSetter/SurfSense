"use client";

import {
	ArrowLeft,
	Check,
	ChevronRight,
	Copy,
	Key,
	type LucideIcon,
	Menu,
	Shield,
	X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useApiKey } from "@/hooks/use-api-key";
import { cn } from "@/lib/utils";

interface SettingsNavItem {
	id: string;
	label: string;
	description: string;
	icon: LucideIcon;
}

function UserSettingsSidebar({
	activeSection,
	onSectionChange,
	onBackToApp,
	isOpen,
	onClose,
	navItems,
}: {
	activeSection: string;
	onSectionChange: (section: string) => void;
	onBackToApp: () => void;
	isOpen: boolean;
	onClose: () => void;
	navItems: SettingsNavItem[];
}) {
	const t = useTranslations("userSettings");

	const handleNavClick = (sectionId: string) => {
		onSectionChange(sectionId);
		onClose();
	};

	return (
		<>
			<AnimatePresence>
				{isOpen && (
					<motion.div
						initial={{ opacity: 0 }}
						animate={{ opacity: 1 }}
						exit={{ opacity: 0 }}
						transition={{ duration: 0.2 }}
						className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
						onClick={onClose}
					/>
				)}
			</AnimatePresence>

			<aside
				className={cn(
					"fixed left-0 top-0 z-50 md:relative md:z-auto",
					"flex h-full w-72 shrink-0 flex-col bg-background md:bg-muted/30",
					"md:border-r",
					"transition-transform duration-300 ease-out",
					"md:translate-x-0",
					isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"
				)}
			>
				{/* Header with title */}
				<div className="space-y-3 p-4">
					<div className="flex items-center justify-between">
						<Button
							variant="ghost"
							onClick={onBackToApp}
							className="group h-11 justify-start gap-3 px-3 hover:bg-muted"
						>
							<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 transition-colors group-hover:bg-primary/20">
								<ArrowLeft className="h-4 w-4 text-primary" />
							</div>
							<span className="font-medium">{t("back_to_app")}</span>
						</Button>
						<Button variant="ghost" size="icon" onClick={onClose} className="h-9 w-9 md:hidden">
							<X className="h-5 w-5" />
						</Button>
					</div>
					{/* Settings Title */}
					<div className="px-3">
						<h2 className="text-lg font-semibold text-foreground">{t("title")}</h2>
					</div>
				</div>

				<nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
					{navItems.map((item, index) => {
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
									"relative flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-all duration-200",
									isActive ? "border border-border bg-muted shadow-sm" : "hover:bg-muted/60"
								)}
							>
								{isActive && (
									<motion.div
										layoutId="userSettingsActiveIndicator"
										className="absolute left-0 top-1/2 h-8 w-1 -translate-y-1/2 rounded-r-full bg-primary"
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
										"flex h-9 w-9 items-center justify-center rounded-lg transition-colors",
										isActive ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground"
									)}
								>
									<Icon className="h-4 w-4" />
								</div>
								<div className="min-w-0 flex-1">
									<p
										className={cn(
											"truncate text-sm font-medium transition-colors",
											isActive ? "text-foreground" : "text-muted-foreground"
										)}
									>
										{item.label}
									</p>
									<p className="truncate text-xs text-muted-foreground/70">{item.description}</p>
								</div>
								<ChevronRight
									className={cn(
										"h-4 w-4 shrink-0 transition-all",
										isActive
											? "translate-x-0 text-primary opacity-100"
											: "-translate-x-1 text-muted-foreground/40 opacity-0"
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

function ApiKeyContent({ onMenuClick }: { onMenuClick: () => void }) {
	const t = useTranslations("userSettings");
	const { apiKey, isLoading, copied, copyToClipboard } = useApiKey();

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ delay: 0.2, duration: 0.4 }}
			className="h-full min-w-0 flex-1 overflow-hidden bg-background"
		>
			<div className="h-full overflow-y-auto">
				<div className="mx-auto max-w-4xl p-4 md:p-6 lg:p-10">
					<AnimatePresence mode="wait">
						<motion.div
							key="api-key-header"
							initial={{ opacity: 0, y: 10 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -10 }}
							transition={{ duration: 0.3 }}
							className="mb-6 md:mb-8"
						>
							<div className="flex items-center gap-3 md:gap-4">
								<Button
									variant="outline"
									size="icon"
									onClick={onMenuClick}
									className="h-10 w-10 shrink-0 md:hidden"
								>
									<Menu className="h-5 w-5" />
								</Button>
								<motion.div
									initial={{ scale: 0.8, opacity: 0 }}
									animate={{ scale: 1, opacity: 1 }}
									transition={{ delay: 0.1, duration: 0.3 }}
									className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-primary/10 bg-gradient-to-br from-primary/20 to-primary/5 shadow-sm md:h-14 md:w-14 md:rounded-2xl"
								>
									<Key className="h-5 w-5 text-primary md:h-7 md:w-7" />
								</motion.div>
								<div className="min-w-0">
									<h1 className="truncate text-lg font-bold tracking-tight md:text-2xl">
										{t("api_key_title")}
									</h1>
									<p className="text-sm text-muted-foreground">{t("api_key_description")}</p>
								</div>
							</div>
						</motion.div>
					</AnimatePresence>

					<AnimatePresence mode="wait">
						<motion.div
							key="api-key-content"
							initial={{ opacity: 0, y: 20 }}
							animate={{ opacity: 1, y: 0 }}
							exit={{ opacity: 0, y: -20 }}
							transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1] }}
							className="space-y-6"
						>
							<Alert>
								<Shield className="h-4 w-4" />
								<AlertTitle>{t("api_key_warning_title")}</AlertTitle>
								<AlertDescription>{t("api_key_warning_description")}</AlertDescription>
							</Alert>

							<div className="rounded-lg border bg-card p-6">
								<h3 className="mb-4 font-medium">{t("your_api_key")}</h3>
								{isLoading ? (
									<div className="h-12 w-full animate-pulse rounded-md bg-muted" />
								) : apiKey ? (
									<div className="flex items-center gap-2">
										<div className="flex-1 overflow-x-auto rounded-md bg-muted p-3 font-mono text-sm">
											{apiKey}
										</div>
										<TooltipProvider>
											<Tooltip>
												<TooltipTrigger asChild>
													<Button
														variant="outline"
														size="icon"
														onClick={copyToClipboard}
														className="shrink-0"
													>
														{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
													</Button>
												</TooltipTrigger>
												<TooltipContent>{copied ? t("copied") : t("copy")}</TooltipContent>
											</Tooltip>
										</TooltipProvider>
									</div>
								) : (
									<p className="text-center text-muted-foreground">{t("no_api_key")}</p>
								)}
							</div>

							<div className="rounded-lg border bg-card p-6">
								<h3 className="mb-2 font-medium">{t("usage_title")}</h3>
								<p className="mb-4 text-sm text-muted-foreground">{t("usage_description")}</p>
								<pre className="overflow-x-auto rounded-md bg-muted p-3 text-sm">
									<code>Authorization: Bearer {apiKey || "YOUR_API_KEY"}</code>
								</pre>
							</div>
						</motion.div>
					</AnimatePresence>
				</div>
			</div>
		</motion.div>
	);
}

export default function UserSettingsPage() {
	const t = useTranslations("userSettings");
	const router = useRouter();
	const [activeSection, setActiveSection] = useState("api-key");
	const [isSidebarOpen, setIsSidebarOpen] = useState(false);

	const navItems: SettingsNavItem[] = [
		{
			id: "api-key",
			label: t("api_key_nav_label"),
			description: t("api_key_nav_description"),
			icon: Key,
		},
	];

	const handleBackToApp = useCallback(() => {
		router.back();
	}, [router]);

	return (
		<motion.div
			initial={{ opacity: 0 }}
			animate={{ opacity: 1 }}
			transition={{ duration: 0.3 }}
			className="fixed inset-0 z-50 flex bg-muted/40"
		>
			<div className="flex h-full w-full p-0 md:p-2">
				<div className="flex h-full w-full overflow-hidden bg-background md:rounded-xl md:border md:shadow-sm">
					<UserSettingsSidebar
						activeSection={activeSection}
						onSectionChange={setActiveSection}
						onBackToApp={handleBackToApp}
						isOpen={isSidebarOpen}
						onClose={() => setIsSidebarOpen(false)}
						navItems={navItems}
					/>
					{activeSection === "api-key" && (
						<ApiKeyContent onMenuClick={() => setIsSidebarOpen(true)} />
					)}
				</div>
			</div>
		</motion.div>
	);
}
