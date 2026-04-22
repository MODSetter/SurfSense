"use client";

import { CheckCircle2 } from "lucide-react";
import type { FC } from "react";
import type { ConnectorConfigProps } from "../index";

export const MCPServiceConfig: FC<ConnectorConfigProps> = ({ connector }) => {
	const serviceName = connector.config?.mcp_service as string | undefined;

	return (
		<div className="space-y-4">
			<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 shrink-0 mt-0.5">
					<CheckCircle2 className="size-4 text-emerald-500" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Connected via MCP</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						Your agent can search, read, and take actions in{" "}
						{serviceName
							? serviceName.charAt(0).toUpperCase() + serviceName.slice(1)
							: "this service"}{" "}
						in real time. No background indexing needed.
					</p>
				</div>
			</div>

		</div>
	);
};
