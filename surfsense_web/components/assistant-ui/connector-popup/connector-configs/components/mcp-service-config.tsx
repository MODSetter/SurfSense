"use client";

import { CheckCircle2 } from "lucide-react";
import type { FC } from "react";
import type { ConnectorConfigProps } from "../index";

export const MCPServiceConfig: FC<ConnectorConfigProps> = ({ connector }) => {
	const serviceName = connector.config?.mcp_service as string | undefined;
	const displayName = serviceName
		? serviceName.charAt(0).toUpperCase() + serviceName.slice(1)
		: "this service";

	return (
		<div className="space-y-4">
			<div className="rounded-xl border border-border bg-emerald-500/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 shrink-0 mt-0.5">
					<CheckCircle2 className="size-4 text-emerald-500" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Connected</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						Your agent can search, read, and take actions in {displayName}.
					</p>
				</div>
			</div>
		</div>
	);
};
