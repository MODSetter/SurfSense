"use client";

import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface HeaderProps {
	breadcrumb?: React.ReactNode;
	languageSwitcher?: React.ReactNode;
	theme?: string;
	onToggleTheme?: () => void;
	mobileMenuTrigger?: React.ReactNode;
}

export function Header({
	breadcrumb,
	languageSwitcher,
	theme,
	onToggleTheme,
	mobileMenuTrigger,
}: HeaderProps) {
	return (
		<header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 backdrop-blur supports-backdrop-filter:bg-background/60 px-4">
			{/* Left side - Mobile menu trigger + Breadcrumb */}
			<div className="flex flex-1 items-center gap-2 min-w-0">
				{mobileMenuTrigger}
				<div className="hidden md:block">{breadcrumb}</div>
			</div>

			{/* Right side - Actions */}
			<div className="flex items-center gap-2">
				{/* Theme toggle */}
				{onToggleTheme && (
					<Tooltip>
						<TooltipTrigger asChild>
							<Button variant="outline" size="icon" onClick={onToggleTheme} className="h-8 w-8">
								{theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
								<span className="sr-only">Toggle theme</span>
							</Button>
						</TooltipTrigger>
						<TooltipContent>{theme === "dark" ? "Light mode" : "Dark mode"}</TooltipContent>
					</Tooltip>
				)}

				{languageSwitcher}
			</div>
		</header>
	);
}
