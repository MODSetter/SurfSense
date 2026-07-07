"use client";

import {
	Check,
	ChevronRight,
	ChevronUp,
	Download,
	ExternalLink,
	Info,
	Languages,
	LogOut,
	Megaphone,
	Monitor,
	Moon,
	Sun,
	UserCog,
} from "lucide-react";
import Image from "next/image";
import { useTranslations } from "next-intl";
import type React from "react";
import { Fragment, useState } from "react";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent, DrawerHandle, DrawerTitle } from "@/components/ui/drawer";
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
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useLocaleContext } from "@/contexts/LocaleContext";
import { useMediaQuery } from "@/hooks/use-media-query";
import { usePlatform } from "@/hooks/use-platform";
import { GITHUB_RELEASES_URL, usePrimaryDownload } from "@/lib/desktop-download-utils";
import { APP_VERSION } from "@/lib/env-config";
import { trackDesktopDownloadClicked } from "@/lib/posthog/events";
import { getUserAvatarColor, getUserInitials } from "@/lib/user-avatar";
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
	{ value: "system" as const, name: "System", icon: Monitor },
];

const LEARN_MORE_LINKS = [
	{ key: "documentation" as const, href: "https://www.surfsense.com/docs" },
	{ key: "github" as const, href: "https://github.com/MODSetter/SurfSense" },
];

type MobileProfileSubmenu = "theme" | "language" | "learn_more";

interface SidebarUserProfileProps {
	user: User;
	onUserSettings?: () => void;
	onAnnouncements?: () => void;
	announcementUnreadCount?: number;
	onLogout?: () => void;
	isCollapsed?: boolean;
	theme?: string;
	setTheme?: (theme: "light" | "dark" | "system") => void;
	topContent?: React.ReactNode;
}

function formatAnnouncementCount(count: number): string {
	if (count <= 999) {
		return count.toString();
	}
	const thousands = Math.floor(count / 1000);
	return `${thousands}k+`;
}

/**
 * User avatar component - shows image if available, otherwise falls back to initials
 */
function UserAvatar({
	avatarUrl,
	initials,
	bgColor,
	size = "sm",
}: {
	avatarUrl?: string;
	initials: string;
	bgColor: string;
	size?: "sm" | "md";
}) {
	const sizeClass = size === "md" ? "h-10 w-10" : "h-8 w-8";

	if (avatarUrl) {
		return (
			<Image
				src={avatarUrl}
				alt="User avatar"
				width={size === "md" ? 40 : 32}
				height={size === "md" ? 40 : 32}
				className={cn(sizeClass, "shrink-0 rounded-full object-cover select-none")}
				referrerPolicy="no-referrer"
				unoptimized
			/>
		);
	}

	return (
		<div
			className={cn(
				sizeClass,
				"flex shrink-0 items-center justify-center rounded-full text-xs font-semibold text-white select-none"
			)}
			style={{ backgroundColor: bgColor }}
		>
			{initials}
		</div>
	);
}

export function SidebarUserProfile({
	user,
	onUserSettings,
	onAnnouncements,
	announcementUnreadCount = 0,
	onLogout,
	isCollapsed = false,
	theme,
	setTheme,
	topContent,
}: SidebarUserProfileProps) {
	const t = useTranslations("sidebar");
	const { locale, setLocale } = useLocaleContext();
	const { isDesktop } = usePlatform();
	const isDesktopViewport = useMediaQuery("(min-width: 768px)");
	const { os, primary, isMobileOS } = usePrimaryDownload();
	const [isLoggingOut, setIsLoggingOut] = useState(false);
	const [mobileSubmenu, setMobileSubmenu] = useState<MobileProfileSubmenu | null>(null);
	const bgColor = getUserAvatarColor(user.email);
	const initials = getUserInitials(user.email);
	const displayName = user.name || user.email.split("@")[0];
	const downloadUrl = primary?.url ?? GITHUB_RELEASES_URL;
	const downloadLabel = t("download_for_os", { os });
	const showDownloadCta = !isDesktop && !isMobileOS && isDesktopViewport;
	const useMobileSubmenus = !isDesktopViewport;

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

	const submenuTriggerClassName = "cursor-default";
	const drawerItemClassName = cn(
		"flex h-12 w-full items-center gap-3 rounded-lg px-3 text-left text-sm transition-colors",
		"hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
	);
	const drawerSeparatorClassName = "mx-3 h-px bg-popover-border";

	const renderThemeSubmenu = () => {
		if (!setTheme) return null;

		if (useMobileSubmenus) {
			return (
				<DropdownMenuItem
					className={submenuTriggerClassName}
					onSelect={() => setMobileSubmenu("theme")}
				>
					<Sun className="h-4 w-4" />
					<span className="flex-1">{t("theme")}</span>
					<ChevronRight className="h-4 w-4 text-muted-foreground" />
				</DropdownMenuItem>
			);
		}

		return (
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
										"hover:bg-accent hover:text-accent-foreground",
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
		);
	};

	const renderLanguageSubmenu = () => {
		if (useMobileSubmenus) {
			return (
				<DropdownMenuItem
					className={submenuTriggerClassName}
					onSelect={() => setMobileSubmenu("language")}
				>
					<Languages className="h-4 w-4" />
					<span className="flex-1">{t("language")}</span>
					<ChevronRight className="h-4 w-4 text-muted-foreground" />
				</DropdownMenuItem>
			);
		}

		return (
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
										"hover:bg-accent hover:text-accent-foreground",
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
		);
	};

	const renderLearnMoreSubmenu = () => {
		if (useMobileSubmenus) {
			return (
				<DropdownMenuItem
					className={submenuTriggerClassName}
					onSelect={() => setMobileSubmenu("learn_more")}
				>
					<Info className="h-4 w-4" />
					<span className="flex-1">{t("learn_more")}</span>
					<ChevronRight className="h-4 w-4 text-muted-foreground" />
				</DropdownMenuItem>
			);
		}

		return (
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
						<DropdownMenuSeparator />
						<p className="select-none px-2 py-1 text-xs leading-tight text-muted-foreground/50">
							v{APP_VERSION}
						</p>
					</DropdownMenuSubContent>
				</DropdownMenuPortal>
			</DropdownMenuSub>
		);
	};

	const mobileSubmenuDrawer = (
		<Drawer
			open={mobileSubmenu !== null}
			onOpenChange={(open) => {
				if (!open) setMobileSubmenu(null);
			}}
			shouldScaleBackground={false}
		>
			<DrawerContent
				className="z-80 max-h-[75vh] rounded-t-2xl border bg-popover text-popover-foreground"
				overlayClassName="z-80"
			>
				<DrawerHandle className="mt-3 h-1.5 w-10" />
				<DrawerTitle className="px-4 pb-2 pt-3 text-center text-base font-semibold">
					{mobileSubmenu === "theme"
						? t("theme")
						: mobileSubmenu === "language"
							? t("language")
							: t("learn_more")}
				</DrawerTitle>
				<div className="space-y-1 px-4 pb-6 pt-1">
					{mobileSubmenu === "theme" &&
						setTheme &&
						THEMES.map((themeOption, index) => {
							const Icon = themeOption.icon;
							const isSelected = theme === themeOption.value;
							return (
								<Fragment key={themeOption.value}>
									{index > 0 && <div className={drawerSeparatorClassName} />}
									<button
										type="button"
										className={cn(drawerItemClassName, isSelected && "text-primary")}
										onClick={() => {
											handleThemeChange(themeOption.value);
											setMobileSubmenu(null);
										}}
									>
										<Icon className="h-4 w-4 text-muted-foreground" />
										<span className="flex-1">{t(themeOption.value)}</span>
										{isSelected && <Check className="h-4 w-4 shrink-0" />}
									</button>
								</Fragment>
							);
						})}

					{mobileSubmenu === "language" &&
						LANGUAGES.map((language, index) => {
							const isSelected = locale === language.code;
							return (
								<Fragment key={language.code}>
									{index > 0 && <div className={drawerSeparatorClassName} />}
									<button
										type="button"
										className={cn(drawerItemClassName, isSelected && "text-primary")}
										onClick={() => {
											handleLanguageChange(language.code);
											setMobileSubmenu(null);
										}}
									>
										<span className="text-base">{language.flag}</span>
										<span className="flex-1">{language.name}</span>
										{isSelected && <Check className="h-4 w-4 shrink-0" />}
									</button>
								</Fragment>
							);
						})}

					{mobileSubmenu === "learn_more" && (
						<>
							{LEARN_MORE_LINKS.map((link, index) => (
								<Fragment key={link.key}>
									{index > 0 && <div className={drawerSeparatorClassName} />}
									<a
										href={link.href}
										target="_blank"
										rel="noopener noreferrer"
										className={drawerItemClassName}
										onClick={() => setMobileSubmenu(null)}
									>
										<span className="flex-1">{t(link.key)}</span>
										<ExternalLink className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
									</a>
								</Fragment>
							))}
							<p className="select-none px-3 py-1 text-xs leading-tight text-muted-foreground/50">
								v{APP_VERSION}
							</p>
						</>
					)}
				</div>
			</DrawerContent>
		</Drawer>
	);

	// Collapsed view - just show avatar with dropdown
	if (isCollapsed) {
		return (
			<div className="relative w-full px-1.5 py-2 before:absolute before:inset-x-1.5 before:top-0 before:h-px before:bg-border">
				<div className="flex flex-col items-center gap-2">
					{topContent}
					{showDownloadCta && (
						<Tooltip>
							<TooltipTrigger asChild>
								<Button
									asChild
									variant="ghost"
									size="icon"
									className="h-10 w-10 rounded-lg bg-muted hover:bg-accent"
								>
									<a
										href={downloadUrl}
										target="_blank"
										rel="noopener noreferrer"
										aria-label={downloadLabel}
										onClick={() =>
											trackDesktopDownloadClicked({ os, placement: "sidebar_collapsed" })
										}
									>
										<Download className="h-4 w-4" strokeWidth={2.5} />
									</a>
								</Button>
							</TooltipTrigger>
							<TooltipContent side="right" sideOffset={8}>
								{downloadLabel}
							</TooltipContent>
						</Tooltip>
					)}
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								type="button"
								variant="ghost"
								className={cn(
									"h-10 w-10 rounded-full p-0",
									"transition-opacity hover:bg-transparent hover:opacity-90",
									"focus:outline-none focus-visible:outline-none",
									"data-[state=open]:opacity-90"
								)}
							>
								<UserAvatar
									avatarUrl={user.avatarUrl}
									initials={initials}
									bgColor={bgColor}
									size="md"
								/>
								<span className="sr-only">{displayName}</span>
							</Button>
						</DropdownMenuTrigger>

						<DropdownMenuContent className="w-48" side="right" align="end" sideOffset={8}>
							<DropdownMenuLabel className="px-2 py-1 font-normal">
								<div className="min-w-0">
									{/* <p className="truncate text-sm font-medium">{displayName}</p> */}
									<p className="truncate text-xs font-semibold leading-tight text-muted-foreground">
										{user.email}
									</p>
								</div>
							</DropdownMenuLabel>

							<DropdownMenuItem onClick={onUserSettings}>
								<UserCog className="h-4 w-4" />
								{t("user_settings")}
							</DropdownMenuItem>

							{onAnnouncements && (
								<DropdownMenuItem onClick={onAnnouncements}>
									<Megaphone className="h-4 w-4" />
									<span className="flex-1">What's New</span>
									{announcementUnreadCount > 0 && (
										<span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium">
											{formatAnnouncementCount(announcementUnreadCount)}
										</span>
									)}
								</DropdownMenuItem>
							)}

							{renderThemeSubmenu()}

							{renderLanguageSubmenu()}

							{renderLearnMoreSubmenu()}

							{!isDesktop && !isMobileOS && (
								<DropdownMenuItem asChild className="font-medium">
									<a href={downloadUrl} target="_blank" rel="noopener noreferrer">
										<Download className="h-4 w-4" strokeWidth={2.5} />
										{downloadLabel}
									</a>
								</DropdownMenuItem>
							)}

							<DropdownMenuSeparator />

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
					{mobileSubmenuDrawer}
				</div>
			</div>
		);
	}

	// Expanded view
	return (
		<div className="border-t">
			{showDownloadCta && (
				<Button
					asChild
					variant="ghost"
					className="mx-2 mt-2 mb-1 h-10 w-[calc(100%-1rem)] justify-start gap-2 rounded-md bg-muted px-3 text-sm font-semibold hover:bg-accent"
				>
					<a
						href={downloadUrl}
						target="_blank"
						rel="noopener noreferrer"
						onClick={() => trackDesktopDownloadClicked({ os, placement: "sidebar_expanded" })}
					>
						<Download className="h-4 w-4" strokeWidth={2.5} />
						{downloadLabel}
					</a>
				</Button>
			)}
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						className={cn(
							"h-auto w-full justify-start gap-2 rounded-none px-2 py-3 text-left",
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
					</Button>
				</DropdownMenuTrigger>

				<DropdownMenuContent className="w-48" side="top" align="center" sideOffset={4}>
					<DropdownMenuLabel className="px-2 py-1 font-normal">
						<div className="min-w-0">
							<p className="truncate text-sm font-medium">{displayName}</p>
							<p className="truncate text-xs font-semibold leading-tight text-muted-foreground">
								{user.email}
							</p>
						</div>
					</DropdownMenuLabel>

					<DropdownMenuItem onClick={onUserSettings}>
						<UserCog className="h-4 w-4" />
						{t("user_settings")}
					</DropdownMenuItem>

					{onAnnouncements && (
						<DropdownMenuItem onClick={onAnnouncements}>
							<Megaphone className="h-4 w-4" />
							<span className="flex-1">What's New</span>
							{announcementUnreadCount > 0 && (
								<span className="inline-flex items-center justify-center min-w-4 h-4 px-1 rounded-full bg-red-500 text-white text-[10px] font-medium">
									{formatAnnouncementCount(announcementUnreadCount)}
								</span>
							)}
						</DropdownMenuItem>
					)}

					{renderThemeSubmenu()}

					{renderLanguageSubmenu()}

					{renderLearnMoreSubmenu()}

					{!isDesktop && (
						<DropdownMenuItem asChild className="font-medium">
							<a href={downloadUrl} target="_blank" rel="noopener noreferrer">
								<Download className="h-4 w-4" strokeWidth={2.5} />
								{downloadLabel}
							</a>
						</DropdownMenuItem>
					)}

					<DropdownMenuSeparator />

					<DropdownMenuItem onClick={handleLogout} disabled={isLoggingOut}>
						{isLoggingOut ? <Spinner size="sm" className="mr-2" /> : <LogOut className="h-4 w-4" />}
						{isLoggingOut ? t("loggingOut") : t("logout")}
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
			{mobileSubmenuDrawer}
		</div>
	);
}
