"use client";

import { ChevronRight, Mail } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
	SidebarGroup,
	SidebarGroupContent,
	SidebarGroupLabel,
	useSidebar,
} from "@/components/ui/sidebar";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";

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
			<Collapsible defaultOpen={false} className="group-data-[collapsible=icon]:hidden">
				<CollapsibleTrigger asChild>
					<SidebarGroupLabel className="cursor-pointer hover:bg-sidebar-accent rounded-md px-2 py-1.5 -mx-2 transition-colors flex items-center justify-between group">
						<span>Page Usage</span>
						<ChevronRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-data-[state=open]:rotate-90" />
					</SidebarGroupLabel>
				</CollapsibleTrigger>
				<CollapsibleContent>
					<SidebarGroupContent>
						<div className="space-y-2 px-2 py-2">
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
						</div>
					</SidebarGroupContent>
				</CollapsibleContent>
			</Collapsible>
			{isCollapsed && (
				// Show only a compact progress indicator when sidebar is collapsed
				<SidebarGroupContent>
					<div className="flex justify-center px-2 py-2">
						<Progress value={usagePercentage} className="h-2 w-8" />
					</div>
				</SidebarGroupContent>
			)}
		</SidebarGroup>
	);
}