"use client";

import { AutoReloadSettings } from "@/components/settings/auto-reload-settings";
import { BuyCreditsContent } from "@/components/settings/buy-credits-content";
import { PlanUpgradeCard } from "@/components/settings/plan-upgrade-card";

export default function BuyMorePage() {
	return (
		<div className="flex min-h-[37rem] w-full select-none items-center justify-center py-8">
			<div className="w-full max-w-md space-y-8">
				{/* Above the credit packs on purpose: at $15 for $6 of included usage
				    plus connectors and crawls, Pro is the better deal for anyone
				    about to buy more than a few dollars of credit. */}
				<PlanUpgradeCard />
				<BuyCreditsContent />
				<AutoReloadSettings />
			</div>
		</div>
	);
}
