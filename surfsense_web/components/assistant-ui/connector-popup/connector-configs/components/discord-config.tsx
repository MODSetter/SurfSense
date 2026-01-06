"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import type { ConnectorConfigProps } from "../index";

export interface DiscordConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const DiscordConfig: FC<DiscordConfigProps> = () => {
	return (
		<div className="space-y-6">
			<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
					<Info className="size-4" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Add Bot to Servers</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						Before indexing, make sure the Discord bot has been added to the servers (guilds) you
						want to index. The bot can only access messages from servers it's been added to. Use the
						OAuth authorization flow to add the bot to your servers.
					</p>
				</div>
			</div>
		</div>
	);
};
