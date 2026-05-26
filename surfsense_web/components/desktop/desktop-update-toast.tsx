"use client";

import { Download, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type UpdateToastState = {
	version: string;
};

export function DesktopUpdateToast() {
	const [update, setUpdate] = useState<UpdateToastState | null>(null);

	useEffect(() => {
		const api = window.electronAPI;
		if (!api?.onUpdateDownloaded) return;

		return api.onUpdateDownloaded(({ version }) => {
			setUpdate({ version });
		});
	}, []);

	if (!update) return null;

	const installAndRestart = () => {
		void window.electronAPI?.installUpdateNow();
	};

	return (
		<div className="pointer-events-none fixed bottom-5 right-5 z-[100]">
			<div
				className={cn(
					"pointer-events-auto relative flex w-[360px] max-w-[calc(100vw-2.5rem)] gap-3 rounded-md border border-popover-border",
					"bg-popover p-4 text-popover-foreground shadow-md"
				)}
				aria-live="polite"
			>
				<div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground">
					<Download className="size-5" strokeWidth={1.8} />
				</div>

				<div className="min-w-0 flex-1">
					<div className="pr-8 text-sm font-semibold tracking-tight">Update available</div>
					<p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
						A new version of SurfSense ({update.version}) is now available to install.
					</p>

					<div className="mt-3 flex items-center gap-4">
						<Button
							type="button"
							variant="ghost"
							className="h-auto px-0 text-sm font-semibold hover:bg-transparent hover:text-foreground"
							onClick={installAndRestart}
						>
							Install and restart
						</Button>
						<Button
							type="button"
							variant="ghost"
							className="h-auto px-0 text-sm font-semibold text-muted-foreground hover:bg-transparent hover:text-foreground"
							onClick={() => setUpdate(null)}
						>
							Not now
						</Button>
					</div>
				</div>

				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="absolute right-2 top-2 size-7 text-muted-foreground hover:bg-transparent hover:text-foreground"
					aria-label="Dismiss update toast"
					onClick={() => setUpdate(null)}
				>
					<X className="size-4" strokeWidth={1.8} />
				</Button>
			</div>
		</div>
	);
}
