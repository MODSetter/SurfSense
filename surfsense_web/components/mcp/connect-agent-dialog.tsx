"use client";

import { Cable } from "lucide-react";
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
				<Cable className="h-3.5 w-3.5 shrink-0" />
				<span className="min-w-0 flex-1 truncate">Connect your agent</span>
			</DialogTrigger>
			<DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
				<DialogHeader>
					<DialogTitle>Connect to Claude Code, Codex, OpenCode…</DialogTitle>
					<DialogDescription>
						The SurfSense MCP server gives any coding agent these scrapers and your knowledge base
						as native tools. You need an API key (create one under API Keys) — then pick your agent
						and paste its config.
					</DialogDescription>
				</DialogHeader>
				<AgentSetupTabs options={{ baseUrl: BACKEND_URL || undefined }} />
			</DialogContent>
		</Dialog>
	);
}
