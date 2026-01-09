"use client";

import { Info } from "lucide-react";
import type { FC } from "react";
import type { ConnectorConfigProps } from "../index";

export interface TeamsConfigProps extends ConnectorConfigProps {
	onNameChange?: (name: string) => void;
}

export const TeamsConfig: FC<TeamsConfigProps> = () => {
	return (
		<div className="space-y-6">
			<div className="rounded-xl border border-border bg-primary/5 p-4 flex items-start gap-3">
				<div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 shrink-0 mt-0.5">
					<Info className="size-4" />
				</div>
				<div className="text-xs sm:text-sm">
					<p className="font-medium text-xs sm:text-sm">Microsoft Teams Access</p>
					<p className="text-muted-foreground mt-1 text-[10px] sm:text-sm">
						SurfSense will index messages from Teams channels that you have access to. The app can
						only read messages from teams and channels where you are a member. Make sure you're a
						member of the teams you want to index before connecting.
					</p>
				</div>
			</div>
		</div>
	);
};
