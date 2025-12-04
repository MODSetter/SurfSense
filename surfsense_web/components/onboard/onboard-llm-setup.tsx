"use client";

import { Bot } from "lucide-react";
import { motion } from "motion/react";
import { Logo } from "@/components/Logo";
import { SetupLLMStep } from "@/components/onboard/setup-llm-step";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface OnboardLLMSetupProps {
	searchSpaceId: number;
	title: string;
	configTitle: string;
	configDescription: string;
	onConfigCreated: () => void;
	onConfigDeleted: () => void;
	onPreferencesUpdated: () => Promise<void>;
}

export function OnboardLLMSetup({
	searchSpaceId,
	title,
	configTitle,
	configDescription,
	onConfigCreated,
	onConfigDeleted,
	onPreferencesUpdated,
}: OnboardLLMSetupProps) {
	return (
		<div className="min-h-screen bg-background flex items-center justify-center p-4">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.5 }}
				className="w-full max-w-4xl"
			>
				{/* Header */}
				<div className="text-center mb-8">
					<motion.div
						initial={{ scale: 0 }}
						animate={{ scale: 1 }}
						transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
						className="inline-flex items-center justify-center mb-6"
					>
						<Logo className="w-16 h-16 rounded-2xl shadow-lg" />
					</motion.div>
					<motion.h1
						initial={{ opacity: 0, y: 10 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: 0.2 }}
						className="text-4xl font-bold text-foreground mb-3"
					>
						{title}
					</motion.h1>
					<motion.p
						initial={{ opacity: 0, y: 10 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: 0.3 }}
						className="text-muted-foreground text-lg"
					>
						Configure your AI model to get started
					</motion.p>
				</div>

				{/* LLM Setup Card */}
				<motion.div
					initial={{ opacity: 0, y: 20 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.4 }}
				>
					<Card className="shadow-lg">
						<CardHeader className="text-center border-b pb-6">
							<div className="flex items-center justify-center gap-3 mb-2">
								<div className="p-2 rounded-xl bg-primary/10 border border-primary/20">
									<Bot className="w-6 h-6 text-primary" />
								</div>
								<CardTitle className="text-2xl">{configTitle}</CardTitle>
							</div>
							<CardDescription>{configDescription}</CardDescription>
						</CardHeader>
						<CardContent className="pt-6">
							<SetupLLMStep
								searchSpaceId={searchSpaceId}
								onConfigCreated={onConfigCreated}
								onConfigDeleted={onConfigDeleted}
								onPreferencesUpdated={onPreferencesUpdated}
							/>
						</CardContent>
					</Card>
				</motion.div>
			</motion.div>
		</div>
	);
}
