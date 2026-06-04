"use client";

import { useState } from "react";
import { BuyPagesContent } from "@/components/settings/buy-pages-content";
import { BuyTokensContent } from "@/components/settings/buy-tokens-content";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const TABS = [
	{ id: "pages", label: "Pages" },
	{ id: "tokens", label: "Premium Credit" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function BuyMorePage() {
	const [activeTab, setActiveTab] = useState<TabId>("pages");

	return (
		<div className="w-full select-none">
			<Tabs
				value={activeTab}
				onValueChange={(value) => {
					setActiveTab(value as TabId);
				}}
				className="relative min-h-[37rem] w-full"
			>
				<TabsList className="absolute top-20 left-1/2 -translate-x-1/2 rounded-xl bg-accent p-1">
					{TABS.map((tab) => (
						<TabsTrigger
							key={tab.id}
							value={tab.id}
							className="h-8 rounded-lg px-4 text-sm font-semibold text-accent-foreground transition-colors hover:bg-transparent hover:text-white data-[state=active]:bg-[#4a4a4a] data-[state=active]:text-white data-[state=active]:shadow-none"
						>
							{tab.label}
						</TabsTrigger>
					))}
				</TabsList>

				<TabsContent value="pages" className="mt-0 flex min-h-[37rem] items-center pt-14">
					<BuyPagesContent />
				</TabsContent>
				<TabsContent value="tokens" className="mt-0 flex min-h-[37rem] items-center pt-14">
					<BuyTokensContent />
				</TabsContent>
			</Tabs>
		</div>
	);
}
