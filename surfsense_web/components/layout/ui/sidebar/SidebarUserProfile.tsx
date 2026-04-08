"use client";

import {
	Check,
	ChevronUp,
	ExternalLink,
	Info,
	Languages,
	Laptop,
	LogOut,
	Moon,
	Sun,
	UserCog,
} from "lucide-react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import { useState } from "react";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuPortal,
	DropdownMenuSeparator,
	DropdownMenuSub,
	DropdownMenuSubContent,
	DropdownMenuSubTrigger,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Spinner } from "@/components/ui/spinner";
import { useLocaleContext } from "@/contexts/LocaleContext";
import { APP_VERSION } from "@/lib/env-config";
import { cn } from "@/lib/utils";
import type { User } from "../../types/layout.types";

// Supported languages configuration
const LANGUAGES = [
	{ code: "en" as const, name: "English", flag: "🇺🇸" },
	{ code: "es" as const, name: "Español", flag: "🇪🇸" },
	{ code: "pt" as const, name: "Português", flag: "🇧🇷" },
	{ code: "hi" as const, name: "हिन्दी", flag: "🇮🇳" },
	{ code: "zh" as const, name: "简体中文", flag: "🇨🇳" },
];

// Supported themes configuration
const THEMES = [
	{ value: "light" as const, name: "Light", icon: Sun },
	{ value: "dark" as const, name: "Dark", icon: Moon },
	{ value: "system" as const, name: "System", icon: Laptop },
];

const LEARN_MORE_LINKS = [
	{ key: "documentation" as const, href: "https://surfsense.com/docs" },
	{ key: "github" as const, href: "https://github.com/MODSetter/SurfSense" },
];

interface SidebarUserProfileProps {
	user: User;
	onUserSettings?: () => void;
	onLogout?: () => void;
	isCollapsed?: boolean;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
}

/**
 * Generates a consistent color based on email
 */
function stringToColor(str: string): string {
	let hash = 0;
	for (let i = 0; i < str.length; i++) {
		hash = str.charCodeAt(i) + ((hash << 5) - hash);
	}
	const colors = [
		"#6366f1",
		"#8b5cf6",
		"#a855f7",
		"#d946ef",
		"#ec4899",
		"#f43f5e",
		"#ef4444",
		"#f97316",
		"#eab308",
		"#84cc16",
		"#22c55e",
		"#14b8a6",
		"#06b6d4",
		"#0ea5e9",
		"#3b82f6",
	];
	return colors[Math.abs(hash) % colors.length];
}

/**
 * Gets initials from email
 */
function getInitials(email: string): string {
	const name = email.split("@")[0];
	const parts = name.split(/[._-]/);
	if (parts.length >= 2) {
		return (parts[0][0] + parts[1][0]).toUpperCase();
	}
	return name.slice(0, 2).toUpperCase();
}

/**
 * User avatar component - shows image if available, otherwise falls back to initials
 */
function UserAvatar({
	avatarUrl,
	initials,
	bgColor,
}: {
	avatarUrl?: string;
	initials: string;
	bgColor: string;
}) {
	if (avatarUrl) {
		return (
			<Image
				src={avatarUrl}
				alt="User avatar"
				width={32}
				height={32}
				className="h-8 w-8 shrink-0 rounded-lg object-cover select-none"
				referrerPolicy="no-referrer"
				unoptimized
			/>
		);
	}

	return (
		<div
			className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold text-white select-none"
			style={{ backgroundColor: bgColor }}
		>
			{initials}
		</div>
	);
}

export function SidebarUserProfile({
	user,
	onUserSettings,
	onLogout,
	isCollapsed = false,
	theme,
	setTheme,
}: SidebarUserProfileProps) {
	const t = useTranslations("sidebar");
	const { locale, setLocale } = useLocaleContext();
	const [isLoggingOut, setIsLoggingOut] = useState(false);
	const bgColor = stringToColor(user.email);
	const initials = getInitials(user.email);
	const displayName = user.name || user.email.split("@")[0];

	const handleLanguageChange = (newLocale: "en" | "es" | "pt" | "hi" | "zh") => {
		setLocale(newLocale);
	};

	const handleThemeChange = (newTheme: "light" | "dark" | "system") => {
		setTheme?.(newTheme);
	};

	const handleLogout = async () => {
		if (isLoggingOut || !onLogout) return;
		setIsLoggingOut(true);
		try {
			await onLogout();
		} finally {
			setIsLoggingOut(false);
		}
	};

	// Collapsed view - just show avatar with dropdown
	if (isCollapsed) {
		return (
			<div className="border-t p-2">
				<DropdownMenu>
					<DropdownMenuTrigger asChild>
						<button
							type="button"
							className={cn(
								"flex h-10 w-full items-center justify-center rounded-md",
								"hover:bg-accent transition-colors",
								"focus:outline-none focus-visible:outline-none",
								"data-[state=open]:bg-transparent"
							)}
						>
							<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />
							<span className="sr-only">{displayName}</span>
						</button>
					</DropdownMenuTrigger>

					<DropdownMenuContent className="w-48" side="right" align="center" sideOffset={8}>
						<DropdownMenuLabel className="font-normal">
							<div className="flex items-center gap-2">
								<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />
								<div className="flex-1 min-w-0">
									<p className="truncate text-sm font-medium">{displayName}</p>
									<p className="truncate text-xs text-muted-foreground">{user.email}</p>
								</div>
							</div>
						</DropdownMenuLabel>

						<DropdownMenuSeparator className="dark:bg-neutral-700" />

						<DropdownMenuItem onClick={onUserSettings}>
							<UserCog className="h-4 w-4" />
							{t("user_settings")}
						</DropdownMenuItem>

						{setTheme && (
							<DropdownMenuSub>
								<DropdownMenuSubTrigger>
									<Sun className="h-4 w-4" />
									{t("theme")}
								</DropdownMenuSubTrigger>
								<DropdownMenuPortal>
									<DropdownMenuSubContent className="gap-1">
										{THEMES.map((themeOption) => {
											const Icon = themeOption.icon;
											const isSelected = theme === themeOption.value;
											return (
												<DropdownMenuItem
													key={themeOption.value}
													onClick={() => handleThemeChange(themeOption.value)}
													className={cn(
														"mb-1 last:mb-0 transition-all",
														"hover:bg-accent/50",
														isSelected && "text-primary"
													)}
												>
													<Icon className="h-4 w-4" />
													<span className="flex-1">{t(themeOption.value)}</span>
													{isSelected && <Check className="h-4 w-4 shrink-0" />}
												</DropdownMenuItem>
											);
										})}
									</DropdownMenuSubContent>
								</DropdownMenuPortal>
							</DropdownMenuSub>
						)}

						<DropdownMenuSub>
							<DropdownMenuSubTrigger>
								<Languages className="h-4 w-4" />
								{t("language")}
							</DropdownMenuSubTrigger>
							<DropdownMenuPortal>
								<DropdownMenuSubContent className="gap-1">
									{LANGUAGES.map((language) => {
										const isSelected = locale === language.code;
										return (
											<DropdownMenuItem
												key={language.code}
												onClick={() => handleLanguageChange(language.code)}
												className={cn(
													"mb-1 last:mb-0 transition-all",
													"hover:bg-accent/50",
													isSelected && "text-primary"
												)}
											>
												<span className="mr-2">{language.flag}</span>
												<span className="flex-1">{language.name}</span>
												{isSelected && <Check className="h-4 w-4 shrink-0" />}
											</DropdownMenuItem>
										);
									})}
								</DropdownMenuSubContent>
							</DropdownMenuPortal>
						</DropdownMenuSub>

						<DropdownMenuSub>
							<DropdownMenuSubTrigger>
								<Info className="h-4 w-4" />
								{t("learn_more")}
							</DropdownMenuSubTrigger>
							<DropdownMenuPortal>
								<DropdownMenuSubContent className="min-w-[180px] gap-1">
									{LEARN_MORE_LINKS.map((link) => (
										<DropdownMenuItem key={link.key} asChild>
											<a href={link.href} target="_blank" rel="noopener noreferrer">
												<span className="flex-1">{t(link.key)}</span>
												<ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
											</a>
										</DropdownMenuItem>
									))}
									<DropdownMenuSeparator className="dark:bg-neutral-700" />
									<p className="select-none px-2 py-1.5 text-xs text-muted-foreground/50">
										v{APP_VERSION}
									</p>
								</DropdownMenuSubContent>
							</DropdownMenuPortal>
						</DropdownMenuSub>

						<DropdownMenuSeparator className="dark:bg-neutral-700" />

						<DropdownMenuItem onClick={handleLogout} disabled={isLoggingOut}>
							{isLoggingOut ? (
								<Spinner size="sm" className="mr-2" />
							) : (
								<LogOut className="h-4 w-4" />
							)}
							{isLoggingOut ? t("loggingOut") : t("logout")}
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</div>
		);
	}

	// Expanded view
	return (
		<div className="border-t">
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<button
						type="button"
						className={cn(
							"flex w-full items-center gap-2 px-2 py-3 text-left",
							"hover:bg-accent transition-colors",
							"focus:outline-none focus-visible:outline-none",
							"data-[state=open]:bg-transparent"
						)}
					>
						<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />

						{/* Name and email */}
						<div className="flex-1 min-w-0">
							<p className="truncate text-sm font-medium">{displayName}</p>
							<p className="truncate text-xs text-muted-foreground">{user.email}</p>
						</div>

						{/* Chevron icon */}
						<ChevronUp className="h-4 w-4 shrink-0 text-muted-foreground" />
					</button>
				</DropdownMenuTrigger>

				<DropdownMenuContent className="w-48" side="top" align="center" sideOffset={4}>
					<DropdownMenuLabel className="font-normal">
						<div className="flex items-center gap-2">
							<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />
							<div className="flex-1 min-w-0">
								<p className="truncate text-sm font-medium">{displayName}</p>
								<p className="truncate text-xs text-muted-foreground">{user.email}</p>
							</div>
						</div>
					</DropdownMenuLabel>

					<DropdownMenuSeparator className="dark:bg-neutral-700" />

					<DropdownMenuItem onClick={onUserSettings}>
						<UserCog className="h-4 w-4" />
						{t("user_settings")}
					</DropdownMenuItem>

					{setTheme && (
						<DropdownMenuSub>
							<DropdownMenuSubTrigger>
								<Sun className="h-4 w-4" />
								{t("theme")}
							</DropdownMenuSubTrigger>
							<DropdownMenuPortal>
								<DropdownMenuSubContent className="gap-1">
									{THEMES.map((themeOption) => {
										const Icon = themeOption.icon;
										const isSelected = theme === themeOption.value;
										return (
											<DropdownMenuItem
												key={themeOption.value}
												onClick={() => handleThemeChange(themeOption.value)}
												className={cn(
													"mb-1 last:mb-0 transition-all",
													"hover:bg-accent/50",
													isSelected && "text-primary"
												)}
											>
												<Icon className="h-4 w-4" />
												<span className="flex-1">{t(themeOption.value)}</span>
												{isSelected && <Check className="h-4 w-4 shrink-0" />}
											</DropdownMenuItem>
										);
									})}
								</DropdownMenuSubContent>
							</DropdownMenuPortal>
						</DropdownMenuSub>
					)}

					<DropdownMenuSub>
						<DropdownMenuSubTrigger>
							<Languages className="h-4 w-4" />
							{t("language")}
						</DropdownMenuSubTrigger>
						<DropdownMenuPortal>
							<DropdownMenuSubContent className="gap-1">
								{LANGUAGES.map((language) => {
									const isSelected = locale === language.code;
									return (
										<DropdownMenuItem
											key={language.code}
											onClick={() => handleLanguageChange(language.code)}
											className={cn(
												"mb-1 last:mb-0 transition-all",
												"hover:bg-accent/50",
												isSelected && "text-primary"
											)}
										>
											<span className="mr-2">{language.flag}</span>
											<span className="flex-1">{language.name}</span>
											{isSelected && <Check className="h-4 w-4 shrink-0" />}
										</DropdownMenuItem>
									);
								})}
							</DropdownMenuSubContent>
						</DropdownMenuPortal>
					</DropdownMenuSub>

					<DropdownMenuSub>
						<DropdownMenuSubTrigger>
							<Info className="h-4 w-4" />
							{t("learn_more")}
						</DropdownMenuSubTrigger>
						<DropdownMenuPortal>
							<DropdownMenuSubContent className="min-w-[180px] gap-1">
								{LEARN_MORE_LINKS.map((link) => (
									<DropdownMenuItem key={link.key} asChild>
										<a href={link.href} target="_blank" rel="noopener noreferrer">
											<span className="flex-1">{t(link.key)}</span>
											<ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
										</a>
									</DropdownMenuItem>
								))}
								<DropdownMenuSeparator className="dark:bg-neutral-700" />
								<p className="select-none px-2 py-1.5 text-xs text-muted-foreground/50">
									v{APP_VERSION}
								</p>
							</DropdownMenuSubContent>
						</DropdownMenuPortal>
					</DropdownMenuSub>

					<DropdownMenuSeparator className="dark:bg-neutral-700" />

					<DropdownMenuItem onClick={handleLogout} disabled={isLoggingOut}>
						{isLoggingOut ? <Spinner size="sm" className="mr-2" /> : <LogOut className="h-4 w-4" />}
						{isLoggingOut ? t("loggingOut") : t("logout")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
