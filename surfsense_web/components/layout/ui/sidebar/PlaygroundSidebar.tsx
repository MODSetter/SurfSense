"use client";

import { History, KeyRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ConnectAgentDialog } from "@/components/mcp/connect-agent-dialog";
import { PLAYGROUND_PLATFORMS, type PlatformIcon } from "@/lib/playground/catalog";
import { cn } from "@/lib/utils";

interface PlaygroundSidebarProps {
	workspaceId: number | string;
}

function PlaygroundNavLink({
	href,
	label,
	icon: Icon,
	isActive,
	indented = false,
}: {
	href: string;
	label: string;
	icon?: PlatformIcon;
	isActive: boolean;
	indented?: boolean;
}) {
	return (
		<Link
			href={href}
			aria-current={isActive ? "page" : undefined}
			className={cn(
				"group/link relative flex h-9 items-center gap-2 rounded-md mx-2 px-2 text-sm text-left",
				"transition-colors hover:bg-accent hover:text-accent-foreground",
				"focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
				indented && "pl-8",
				isActive && "bg-accent text-accent-foreground"
			)}
		>
			{Icon ? <Icon className="h-3.5 w-3.5 shrink-0" /> : null}
			<span className="min-w-0 flex-1 truncate">{label}</span>
		</Link>
	);
}

export function PlaygroundSidebar({ workspaceId }: PlaygroundSidebarProps) {
	const pathname = usePathname();
	const base = `/dashboard/${workspaceId}/playground`;

	return (
		<div className="relative flex h-full w-[240px] flex-col bg-panel text-sidebar-foreground overflow-hidden select-none">
			<div className="flex h-12 shrink-0 items-center px-4">
				<span className="text-sm font-semibold">API Playground</span>
			</div>

			<div className="flex flex-col gap-0.5 pt-1.5 pb-1.5 after:mx-3 after:mt-1.5 after:block after:h-px after:bg-border">
				<PlaygroundNavLink
					href={`${base}/runs`}
					label="Runs"
					icon={History}
					isActive={pathname === `${base}/runs`}
				/>
				<PlaygroundNavLink
					href={`${base}/api-keys`}
					label="API Keys"
					icon={KeyRound}
					isActive={pathname === `${base}/api-keys`}
				/>
			</div>

			<div className="flex-1 w-full min-h-0 overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-muted-foreground/20 scrollbar-track-transparent pb-2">
				{PLAYGROUND_PLATFORMS.map((platform) => (
					<div key={platform.id} className="flex flex-col gap-0.5 pt-2">
						<div className="flex items-center gap-2 pl-4 pr-2.5 py-1 text-xs font-medium text-muted-foreground">
							<platform.icon className="h-3.5 w-3.5 shrink-0" />
							<span className="truncate">{platform.label}</span>
						</div>
						{platform.verbs.map((verb) => {
							const href = `${base}/${platform.id}/${verb.verb}`;
							return (
								<PlaygroundNavLink
									key={verb.name}
									href={href}
									label={verb.label}
									isActive={pathname === href}
									indented
								/>
							);
						})}
					</div>
				))}
			</div>

			<div className="shrink-0 py-1.5 before:mx-3 before:mb-1.5 before:block before:h-px before:bg-border">
				<ConnectAgentDialog />
			</div>
		</div>
	);
}
