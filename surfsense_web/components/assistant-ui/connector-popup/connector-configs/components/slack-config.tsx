"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import type { ConnectorConfigProps } from "../index";

export interface SlackConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const SlackConfig: FC<SlackConfigProps> = () => {
	return (
		<div className="space-y-6">
			<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
					<Info className="size-4" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Add Bot to Channels</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						Before indexing, add the SurfSense bot to each channel you want to index. The bot can
						only access messages from channels it's been added to. Type{" "}
						<code className="bg-muted px-1 py-0.5 rounded text-[9px]">/invite @SurfSense</code> in
						any channel to add it.
					</p>
				</div>
			</div>
		</div>
	);
};
