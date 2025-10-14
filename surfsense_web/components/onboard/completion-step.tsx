"use client";

import { ArrowRight, Bot, Brain, CheckCircle, Sparkles, Zap } from "lucide-react";
import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";

const ROLE_ICONS = {
	long_context: Brain,
	fast: Zap,
	strategic: Bot,
};

interface CompletionStepProps {
	searchSpaceId: number;
}

export function CompletionStep({ searchSpaceId }: CompletionStepProps) {
	const { llmConfigs } = useLLMConfigs(searchSpaceId);
	const { preferences } = useLLMPreferences(searchSpaceId);

	const assignedConfigs = {
		long_context: llmConfigs.find((c) => c.id === preferences.long_context_llm_id),
		fast: llmConfigs.find((c) => c.id === preferences.fast_llm_id),
		strategic: llmConfigs.find((c) => c.id === preferences.strategic_llm_id),
	};

	return (
		<div className="space-y-8">
			{/* Success Message */}
			<motion.div
				initial={{ opacity: 0, scale: 0.95 }}
				animate={{ opacity: 1, scale: 1 }}
				transition={{ duration: 0.5 }}
				className="text-center"
			>
				<div className="w-20 h-20 mx-auto mb-6 bg-green-100 rounded-full flex items-center justify-center">
					<CheckCircle className="w-10 h-10 text-green-600" />
				</div>
				<h2 className="text-2xl font-bold mb-2">Setup Complete!</h2>
			</motion.div>

			{/* Configuration Summary */}
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.2 }}
			>
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2">
							<Sparkles className="w-5 h-5" />
							Your LLM Configuration
						</CardTitle>
						<CardDescription>Here's a summary of your setup</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						{Object.entries(assignedConfigs).map(([role, config]) => {
							if (!config) return null;

							const IconComponent = ROLE_ICONS[role as keyof typeof ROLE_ICONS];
							const roleDisplayNames = {
								long_context: "Long Context LLM",
								fast: "Fast LLM",
								strategic: "Strategic LLM",
							};

							return (
								<motion.div
									key={role}
									initial={{ opacity: 0, x: -10 }}
									animate={{ opacity: 1, x: 0 }}
									transition={{ delay: 0.3 + Object.keys(assignedConfigs).indexOf(role) * 0.1 }}
									className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
								>
									<div className="flex items-center gap-3">
										<div className="p-2 bg-background rounded-md">
											<IconComponent className="w-4 h-4" />
										</div>
										<div>
											<p className="font-medium">
												{roleDisplayNames[role as keyof typeof roleDisplayNames]}
											</p>
											<p className="text-sm text-muted-foreground">{config.name}</p>
										</div>
									</div>
									<div className="flex items-center gap-2">
										<Badge variant="outline">{config.provider}</Badge>
										<span className="text-sm text-muted-foreground">{config.model_name}</span>
									</div>
								</motion.div>
							);
						})}
					</CardContent>
				</Card>
			</motion.div>

			{/* Next Steps */}
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.6 }}
			>
				<Card className="border-primary/20 bg-primary/5">
					<CardContent className="pt-6">
						<div className="flex items-center gap-3 mb-4">
							<div className="p-2 bg-primary rounded-md">
								<ArrowRight className="w-4 h-4 text-primary-foreground" />
							</div>
							<h3 className="text-lg font-semibold">Ready to Get Started?</h3>
						</div>
						<p className="text-muted-foreground mb-4">
							Click "Complete Setup" to enter your dashboard and start exploring!
						</p>
						<div className="flex flex-wrap gap-2 text-sm">
							<Badge variant="secondary">
								✓ {llmConfigs.length} LLM provider{llmConfigs.length > 1 ? "s" : ""} configured
							</Badge>
							<Badge variant="secondary">✓ All roles assigned</Badge>
							<Badge variant="secondary">✓ Ready to use</Badge>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		</div>
	);
}
