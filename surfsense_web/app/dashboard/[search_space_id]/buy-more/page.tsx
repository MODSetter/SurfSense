"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { BuyPagesContent } from "@/components/settings/buy-pages-content";
import { BuyTokensContent } from "@/components/settings/buy-tokens-content";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TABS = [
	{ id: "pages", label: "Pages" },
	{ id: "tokens", label: "Premium Credit" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function BuyMorePage() {
	const [activeTab, setActiveTab] = useState<TabId>("pages");

	return (
		<div className="flex min-h-[calc(100vh-64px)] select-none items-center justify-center px-4 py-8">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.3 }}
				className="w-full max-w-md space-y-6"
			>
				<div className="flex items-center justify-center rounded-lg border bg-muted/30 p-1">
					{TABS.map((tab) => (
						<Button
							key={tab.id}
							type="button"
							variant="ghost"
							size="sm"
							onClick={() => setActiveTab(tab.id)}
							className={cn(
								"h-auto flex-1 px-3 py-1.5 text-sm",
								activeTab === tab.id
									? "bg-background text-foreground shadow-sm"
									: "text-muted-foreground hover:text-accent-foreground"
							)}
						>
							{tab.label}
						</Button>
					))}
				</div>

				{activeTab === "pages" ? <BuyPagesContent /> : <BuyTokensContent />}
			</motion.div>
		</div>
	);
}
