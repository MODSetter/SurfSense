"use client";

import { BuyCreditsContent } from "@/components/settings/buy-credits-content";

export default function BuyMorePage() {
	return (
		<div className="flex min-h-[37rem] w-full select-none items-center justify-center">
			<div className="w-full max-w-md">
				<BuyCreditsContent />
			</div>
		</div>
	);
}
