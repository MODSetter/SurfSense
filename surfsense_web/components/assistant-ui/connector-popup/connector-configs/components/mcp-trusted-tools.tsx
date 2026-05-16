"use client";

import { ShieldCheck, Trash2 } from "lucide-react";
import type { FC } from "react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import type { SearchSourceConnector } from "@/contracts/types/connector.types";
import { connectorsApiService } from "@/lib/apis/connectors-api.service";

interface MCPTrustedToolsProps {
	connector: SearchSourceConnector;
}

/** Audit + revoke surface for tools promoted via in-chat "Always Allow". */
export const MCPTrustedTools: FC<MCPTrustedToolsProps> = ({ connector }) => {
	const trustedTools = readTrustedTools(connector.config);
	const [pending, setPending] = useState<Set<string>>(new Set());

	const handleRevoke = async (toolName: string) => {
		setPending((prev) => new Set(prev).add(toolName));
		try {
			await connectorsApiService.untrustMCPTool(connector.id, toolName);
			toast.success(`Removed ${toolName} from trusted tools`);
		} catch {
			toast.error(`Failed to remove ${toolName} from trusted tools`);
		} finally {
			setPending((prev) => {
				const next = new Set(prev);
				next.delete(toolName);
				return next;
			});
		}
	};

	return (
		<div className="space-y-4">
			<h3 className="font-medium text-sm sm:text-base flex items-center gap-2">
				<ShieldCheck className="h-4 w-4" />
				Trusted Tools
			</h3>

			<div className="rounded-xl border border-border bg-slate-400/5 dark:bg-white/5 p-3 sm:p-6 space-y-4">
				<p className="text-[10px] sm:text-xs text-muted-foreground">
					Tools listed here skip the approval prompt during chat. Trust is granted by clicking
					"Always Allow" on an approval card; revoke it here to require approval again.
				</p>

				{trustedTools.length === 0 ? (
					<p className="text-xs text-muted-foreground/70 italic">
						No trusted tools yet for this connector.
					</p>
				) : (
					<ul className="space-y-1">
						{trustedTools.map((toolName) => {
							const isPending = pending.has(toolName);
							return (
								<li
									key={toolName}
									className="flex items-center justify-between gap-3 rounded-lg px-3 py-2 hover:bg-muted/40 transition-colors"
								>
									<span className="text-xs font-mono break-all">{toolName}</span>
									<Button
										type="button"
										variant="ghost"
										size="sm"
										className="h-7 px-2 text-muted-foreground hover:text-destructive shrink-0"
										onClick={() => handleRevoke(toolName)}
										disabled={isPending}
										aria-label={`Revoke trust for ${toolName}`}
									>
										<Trash2 className="h-3.5 w-3.5" />
										<span className="ml-1 hidden sm:inline">Revoke</span>
									</Button>
								</li>
							);
						})}
					</ul>
				)}
			</div>
		</div>
	);
};

function readTrustedTools(config: Record<string, unknown> | undefined | null): string[] {
	const raw = config?.trusted_tools;
	if (!Array.isArray(raw)) return [];
	return raw.filter((item): item is string => typeof item === "string");
}
