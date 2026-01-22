"use client";

import { Zap } from "lucide-react";
import Image from "next/image";
import type { FC } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ComposioConnectorCardProps {
	id: string;
	title: string;
	description: string;
	connectorCount?: number;
	onConnect: () => void;
}

export const ComposioConnectorCard: FC<ComposioConnectorCardProps> = ({
	id,
	title,
	description,
	connectorCount = 0,
	onConnect,
}) => {
	const hasConnections = connectorCount > 0;

	return (
		<div
			className={cn(
				"group relative flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 w-full border",
				"border-violet-500/20 bg-gradient-to-br from-violet-500/5 to-purple-500/5",
				"hover:border-violet-500/40 hover:from-violet-500/10 hover:to-purple-500/10"
			)}
		>
			<div
				className={cn(
					"flex h-12 w-12 items-center justify-center rounded-lg transition-colors shrink-0 border",
					"bg-gradient-to-br from-violet-500/10 to-purple-500/10 border-violet-500/20"
				)}
			>
				<Image
					src="/connectors/composio.svg"
					alt="Composio"
					width={24}
					height={24}
					className="size-6"
				/>
			</div>
			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-1.5">
					<span className="text-[14px] font-semibold leading-tight truncate">{title}</span>
					<Zap className="size-3.5 text-violet-500" />
				</div>
				{hasConnections ? (
					<p className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1.5">
						<span>
							{connectorCount} {connectorCount === 1 ? "connection" : "connections"}
						</span>
					</p>
				) : (
					<p className="text-[10px] text-muted-foreground mt-1">{description}</p>
				)}
			</div>
			<Button
				size="sm"
				variant={hasConnections ? "secondary" : "default"}
				className={cn(
					"h-8 text-[11px] px-3 rounded-lg shrink-0 font-medium shadow-xs",
					!hasConnections && "bg-violet-600 hover:bg-violet-700 text-white",
					hasConnections &&
						"bg-white text-slate-700 hover:bg-slate-50 border-0 dark:bg-secondary dark:text-secondary-foreground dark:hover:bg-secondary/80"
				)}
				onClick={onConnect}
			>
				{hasConnections ? "Manage" : "Browse"}
			</Button>
		</div>
	);
};
