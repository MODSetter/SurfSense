"use client";

import { Loader2 } from "lucide-react";
import { type FC } from "react";
import { Button } from "@/components/ui/button";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";

interface ConnectorCardProps {
	id: string;
	title: string;
	description: string;
	connectorType: string;
	isConnected?: boolean;
	isConnecting?: boolean;
	onConnect?: () => void;
	onManage?: () => void;
}

export const ConnectorCard: FC<ConnectorCardProps> = ({
	id,
	title,
	description,
	connectorType,
	isConnected = false,
	isConnecting = false,
	onConnect,
	onManage,
}) => {
	return (
		<div className="group relative flex items-center gap-4 p-4 rounded-xl text-left transition-all duration-200 w-full border border-border bg-slate-400/5 dark:bg-white/5 hover:bg-slate-400/10 dark:hover:bg-white/10">
			<div className="flex h-12 w-12 items-center justify-center rounded-lg transition-colors flex-shrink-0 bg-slate-400/5 dark:bg-white/5 border border-slate-400/5 dark:border-white/5">
				{getConnectorIcon(connectorType, "size-6")}
			</div>
			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-2">
					<span className="text-[14px] font-semibold leading-tight">{title}</span>
				</div>
				<p className="text-[11px] text-muted-foreground truncate mt-1">
					{isConnected ? "Connected" : description}
				</p>
			</div>
			<Button
				size="sm"
				variant={isConnected ? "outline" : "default"}
				className="h-8 text-[11px] px-3 rounded-lg flex-shrink-0 font-medium"
				onClick={isConnected ? onManage : onConnect}
				disabled={isConnecting}
			>
				{isConnecting ? (
					<Loader2 className="size-3 animate-spin" />
				) : isConnected ? (
					"Manage"
				) : (
					"Connect"
				)}
			</Button>
		</div>
	);
};

