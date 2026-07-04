"use client";

import { AutoReloadSettings } from "@/components/settings/auto-reload-settings";
import { BuyCreditsContent } from "@/components/settings/buy-credits-content";

export default function BuyMorePage() {
	return (
		<div className="flex min-h-[37rem] w-full select-none items-center justify-center py-8">
			<div className="w-full max-w-md space-y-8">
				<BuyCreditsContent />
				<AutoReloadSettings />
			</div>
		</div>
	);
}
