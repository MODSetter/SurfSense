"use client";

import { SidebarButtonBadge } from "@/components/layout/ui/sidebar/SidebarButton";
import { AgentSetupTabs } from "@/components/mcp/agent-setup-tabs";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { BACKEND_URL } from "@/lib/env-config";
import { cn } from "@/lib/utils";

/**
 * Sidebar-footer button that opens the MCP setup guide: pick an agent
 * (Claude Code, Codex, OpenCode, ...), copy its config, done.
 */
export function ConnectAgentDialog({ className }: { className?: string }) {
	return (
		<Dialog>
			<DialogTrigger
				className={cn(
					"group/link relative flex h-9 items-center gap-2 rounded-md mx-2 px-2 text-sm text-left",
					"transition-colors hover:bg-accent hover:text-accent-foreground",
					"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
					className
				)}
			>
				<span
					aria-hidden="true"
					className="size-3.5 shrink-0 bg-current"
					style={{
						mask: "url('/connectors/modelcontextprotocol.svg') center / contain no-repeat",
						WebkitMask: "url('/connectors/modelcontextprotocol.svg') center / contain no-repeat",
					}}
				/>
				<span className="flex min-w-0 flex-1 items-center gap-1.5">
					<span className="min-w-0 truncate">Connect your agent</span>
					<SidebarButtonBadge>New</SidebarButtonBadge>
				</span>
			</DialogTrigger>
			<DialogContent className="max-h-[85vh] min-w-0 overflow-x-hidden overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Connect to Claude Code, Codex, OpenCode…</DialogTitle>
					<DialogDescription>
						Give your coding agent access to SurfSense scrapers and your knowledge base. Create an API key under API Keys, choose your agent, then paste the config.
					</DialogDescription>
				</DialogHeader>
				<AgentSetupTabs options={{ baseUrl: BACKEND_URL || undefined }} />
			</DialogContent>
		</Dialog>
	);
}
