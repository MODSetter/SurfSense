import type { FC } from "react";

export const LegacyDeliverableToolUI: FC = () => (
	<div role="alert" className="my-4 max-w-lg rounded-xl border bg-muted/30 px-5 py-4">
		<p className="text-sm font-semibold text-destructive">Content unavailable</p>
		<p className="mt-1 text-xs text-muted-foreground">
			This content can’t be opened. Ask me to regenerate it.
		</p>
	</div>
);
