"use client";

import { ChevronDown, MessageSquare, Settings2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { SetupLLMStep } from "@/components/onboard/setup-llm-step";
import { SetupPromptStep } from "@/components/onboard/setup-prompt-step";
import { Card, CardContent } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

interface OnboardAdvancedSettingsProps {
	searchSpaceId: number;
	showLLMSettings: boolean;
	setShowLLMSettings: (show: boolean) => void;
	showPromptSettings: boolean;
	setShowPromptSettings: (show: boolean) => void;
	onConfigCreated: () => void;
	onConfigDeleted: () => void;
	onPreferencesUpdated: () => Promise<void>;
}

export function OnboardAdvancedSettings({
	searchSpaceId,
	showLLMSettings,
	setShowLLMSettings,
	showPromptSettings,
	setShowPromptSettings,
	onConfigCreated,
	onConfigDeleted,
	onPreferencesUpdated,
}: OnboardAdvancedSettingsProps) {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ delay: 1 }}
			className="space-y-4"
		>
			{/* LLM Configuration */}
			<Collapsible open={showLLMSettings} onOpenChange={setShowLLMSettings}>
				<CollapsibleTrigger asChild>
					<Card className="hover:bg-muted/50 transition-colors cursor-pointer">
						<CardContent className="py-4">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-3">
									<div className="p-2 rounded-xl bg-fuchsia-500/10 dark:bg-fuchsia-500/20 border border-fuchsia-500/20">
										<Settings2 className="w-5 h-5 text-fuchsia-600 dark:text-fuchsia-400" />
									</div>
									<div>
										<h3 className="font-semibold">LLM Configuration</h3>
										<p className="text-sm text-muted-foreground">
											Customize AI models and role assignments
										</p>
									</div>
								</div>
								<motion.div
									animate={{ rotate: showLLMSettings ? 180 : 0 }}
									transition={{ duration: 0.2 }}
								>
									<ChevronDown className="w-5 h-5 text-muted-foreground" />
								</motion.div>
							</div>
						</CardContent>
					</Card>
				</CollapsibleTrigger>

				<CollapsibleContent>
					<AnimatePresence>
						{showLLMSettings && (
							<motion.div
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: "auto" }}
								exit={{ opacity: 0, height: 0 }}
								transition={{ duration: 0.3 }}
							>
								<Card className="mt-2">
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
						)}
					</AnimatePresence>
				</CollapsibleContent>
			</Collapsible>

			{/* Prompt Configuration */}
			<Collapsible open={showPromptSettings} onOpenChange={setShowPromptSettings}>
				<CollapsibleTrigger asChild>
					<Card className="hover:bg-muted/50 transition-colors cursor-pointer">
						<CardContent className="py-4">
							<div className="flex items-center justify-between">
								<div className="flex items-center gap-3">
									<div className="p-2 rounded-xl bg-cyan-500/10 dark:bg-cyan-500/20 border border-cyan-500/20">
										<MessageSquare className="w-5 h-5 text-cyan-600 dark:text-cyan-400" />
									</div>
									<div>
										<h3 className="font-semibold">AI Response Settings</h3>
										<p className="text-sm text-muted-foreground">
											Configure citations and custom instructions (Optional)
										</p>
									</div>
								</div>
								<motion.div
									animate={{ rotate: showPromptSettings ? 180 : 0 }}
									transition={{ duration: 0.2 }}
								>
									<ChevronDown className="w-5 h-5 text-muted-foreground" />
								</motion.div>
							</div>
						</CardContent>
					</Card>
				</CollapsibleTrigger>

				<CollapsibleContent>
					<AnimatePresence>
						{showPromptSettings && (
							<motion.div
								initial={{ opacity: 0, height: 0 }}
								animate={{ opacity: 1, height: "auto" }}
								exit={{ opacity: 0, height: 0 }}
								transition={{ duration: 0.3 }}
							>
								<Card className="mt-2">
									<CardContent className="pt-6">
										<SetupPromptStep
											searchSpaceId={searchSpaceId}
											onComplete={() => setShowPromptSettings(false)}
										/>
									</CardContent>
								</Card>
							</motion.div>
						)}
					</AnimatePresence>
				</CollapsibleContent>
			</Collapsible>
		</motion.div>
	);
}
