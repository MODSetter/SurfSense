"use client";

import { Mail } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	useSidebar,
} from "@/components/ui/sidebar";

interface PageUsageDisplayProps {
	pagesUsed: number;
	pagesLimit: number;
}

export function PageUsageDisplay({ pagesUsed, pagesLimit }: PageUsageDisplayProps) {
	const { state } = useSidebar();
	const usagePercentage = (pagesUsed / pagesLimit) * 100;
	const isCollapsed = state === "collapsed";

	return (
		<SidebarGroup>
			<SidebarGroupLabel className="group-data-[collapsible=icon]:hidden">
				Page Usage
			</SidebarGroupLabel>
			<SidebarGroupContent>
				<div className="space-y-2 px-2 py-2">
					{isCollapsed ? (
						// Show only a compact progress indicator when collapsed
						<div className="flex justify-center">
							<Progress value={usagePercentage} className="h-2 w-8" />
						</div>
					) : (
						// Show full details when expanded
						<>
							<div className="flex justify-between items-center text-xs">
								<span className="text-muted-foreground">
									{pagesUsed.toLocaleString()} / {pagesLimit.toLocaleString()} pages
								</span>
								<span className="font-medium">{usagePercentage.toFixed(0)}%</span>
							</div>
							<Progress value={usagePercentage} className="h-2" />
							<div className="flex items-start gap-2 pt-1">
								<Mail className="h-3 w-3 text-muted-foreground mt-0.5 flex-shrink-0" />
								<p className="text-[10px] text-muted-foreground leading-tight">
									Contact{" "}
									<a
										href="mailto:rohan@surfsense.com"
										className="text-primary hover:underline font-medium"
									>
										rohan@surfsense.com
									</a>{" "}
									to increase limits
								</p>
							</div>
						</>
					)}
				</div>
			</SidebarGroupContent>
		</SidebarGroup>
	);
}
