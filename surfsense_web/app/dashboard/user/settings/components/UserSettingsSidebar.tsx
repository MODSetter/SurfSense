"use client";

import type { LucideIcon } from "lucide-react";
import { ArrowLeft, ChevronRight, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SettingsNavItem {
	id: string;
	label: string;
	description: string;
	icon: LucideIcon;
}

interface UserSettingsSidebarProps {
	activeSection: string;
	onSectionChange: (section: string) => void;
	onBackToApp: () => void;
	isOpen: boolean;
	onClose: () => void;
	navItems: SettingsNavItem[];
}

export function UserSettingsSidebar({
	activeSection,
	onSectionChange,
	onBackToApp,
	isOpen,
	onClose,
	navItems,
}: UserSettingsSidebarProps) {
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
