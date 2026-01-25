"use client";

import { Check, ChevronUp, Languages, Laptop, LogOut, Moon, Settings, Sun } from "lucide-react";
import { useTranslations } from "next-intl";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useLocaleContext } from "@/contexts/LocaleContext";
import { cn } from "@/lib/utils";
import type { User } from "../../types/layout.types";

// Supported languages configuration
const LANGUAGES = [
	{ code: "en" as const, name: "English", flag: "🇺🇸" },
	{ code: "zh" as const, name: "简体中文", flag: "🇨🇳" },
];

// Supported themes configuration
const THEMES = [
	{ value: "light" as const, name: "Light", icon: Sun },
	{ value: "dark" as const, name: "Dark", icon: Moon },
	{ value: "system" as const, name: "System", icon: Laptop },
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
			<img
				src={avatarUrl}
				alt="User avatar"
				className="h-8 w-8 shrink-0 rounded-lg object-cover"
				referrerPolicy="no-referrer"
			/>
		);
	}

	return (
		<div
			className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-xs font-semibold text-white"
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
	const bgColor = stringToColor(user.email);
	const initials = getInitials(user.email);
	const displayName = user.name || user.email.split("@")[0];

	const handleLanguageChange = (newLocale: "en" | "zh") => {
		setLocale(newLocale);
	};

	const handleThemeChange = (newTheme: "light" | "dark" | "system") => {
		setTheme?.(newTheme);
	};

	// Collapsed view - just show avatar with dropdown
	if (isCollapsed) {
		return (
			<div className="border-t p-2">
				<DropdownMenu>
					<Tooltip>
						<TooltipTrigger asChild>
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
						</TooltipTrigger>
						<TooltipContent side="right">{displayName}</TooltipContent>
					</Tooltip>

					<DropdownMenuContent className="w-56" side="right" align="center" sideOffset={8}>
						<DropdownMenuLabel className="font-normal">
							<div className="flex items-center gap-2">
								<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />
								<div className="flex-1 min-w-0">
									<p className="truncate text-sm font-medium">{displayName}</p>
									<p className="truncate text-xs text-muted-foreground">{user.email}</p>
								</div>
							</div>
						</DropdownMenuLabel>

						<DropdownMenuSeparator />

						<DropdownMenuItem onClick={onUserSettings}>
							<Settings className="mr-2 h-4 w-4" />
							{t("user_settings")}
						</DropdownMenuItem>

						{setTheme && (
							<DropdownMenuSub>
								<DropdownMenuSubTrigger>
									<Sun className="mr-2 h-4 w-4" />
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
													<Icon className="mr-2 h-4 w-4" />
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
								<Languages className="mr-2 h-4 w-4" />
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

						<DropdownMenuSeparator />

						<DropdownMenuItem onClick={onLogout}>
							<LogOut className="mr-2 h-4 w-4" />
							{t("logout")}
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

				<DropdownMenuContent className="w-56" side="top" align="center" sideOffset={4}>
					<DropdownMenuLabel className="font-normal">
						<div className="flex items-center gap-2">
							<UserAvatar avatarUrl={user.avatarUrl} initials={initials} bgColor={bgColor} />
							<div className="flex-1 min-w-0">
								<p className="truncate text-sm font-medium">{displayName}</p>
								<p className="truncate text-xs text-muted-foreground">{user.email}</p>
							</div>
						</div>
					</DropdownMenuLabel>

					<DropdownMenuSeparator />

					<DropdownMenuItem onClick={onUserSettings}>
						<Settings className="mr-2 h-4 w-4" />
						{t("user_settings")}
					</DropdownMenuItem>

					{setTheme && (
						<DropdownMenuSub>
							<DropdownMenuSubTrigger>
								<Sun className="mr-2 h-4 w-4" />
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
												<Icon className="mr-2 h-4 w-4" />
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
							<Languages className="mr-2 h-4 w-4" />
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

					<DropdownMenuSeparator />

					<DropdownMenuItem onClick={onLogout}>
						<LogOut className="mr-2 h-4 w-4" />
						{t("logout")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}
