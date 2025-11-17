"use client";

import {
	ArrowRight,
	Bot,
	Brain,
	CheckCircle,
	FileText,
	MessageSquare,
	Sparkles,
	Zap,
} from "lucide-react";
import { motion } from "motion/react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useGlobalLLMConfigs, useLLMConfigs, useLLMPreferences } from "@/hooks/use-llm-configs";

interface CompletionStepProps {
	searchSpaceId: number;
}

export function CompletionStep({ searchSpaceId }: CompletionStepProps) {
	const router = useRouter();
	const { llmConfigs } = useLLMConfigs(searchSpaceId);
	const { globalConfigs } = useGlobalLLMConfigs();
	const { preferences } = useLLMPreferences(searchSpaceId);

	// Combine global and user-specific configs
	const allConfigs = [...globalConfigs, ...llmConfigs];

	const assignedConfigs = {
		long_context: allConfigs.find((c) => c.id === preferences.long_context_llm_id),
		fast: allConfigs.find((c) => c.id === preferences.fast_llm_id),
		strategic: allConfigs.find((c) => c.id === preferences.strategic_llm_id),
	};

	return (
		<div className="space-y-8">
			{/* Next Steps - What would you like to do? */}
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.6 }}
				className="space-y-4"
			>
				<div className="text-center">
					<h3 className="text-xl font-semibold mb-2">What would you like to do next?</h3>
					<p className="text-muted-foreground">Choose an option to continue</p>
				</div>

				<div className="grid grid-cols-1 md:grid-cols-2 gap-6">
					{/* Add Sources Card */}
					<motion.div
						initial={{ opacity: 0, x: -20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ delay: 0.7 }}
					>
						<Card className="h-full border-2 hover:border-primary/50 transition-all hover:shadow-lg cursor-pointer group">
							<CardHeader>
								<div className="w-12 h-12 bg-blue-100 dark:bg-blue-950 rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
									<FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
								</div>
								<CardTitle className="text-lg">Add Sources</CardTitle>
								<CardDescription>
									Connect your data sources to start building your knowledge base
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2 text-sm text-muted-foreground">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>Connect documents and files</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>Import from various sources</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>Build your knowledge base</span>
									</div>
								</div>
								<Button
									className="w-full group-hover:bg-primary/90"
									onClick={() => router.push(`/dashboard/${searchSpaceId}/sources/add`)}
								>
									Add Sources
									<ArrowRight className="w-4 h-4 ml-2" />
								</Button>
							</CardContent>
						</Card>
					</motion.div>

					{/* Start Chatting Card */}
					<motion.div
						initial={{ opacity: 0, x: 20 }}
						animate={{ opacity: 1, x: 0 }}
						transition={{ delay: 0.8 }}
					>
						<Card className="h-full border-2 hover:border-primary/50 transition-all hover:shadow-lg cursor-pointer group">
							<CardHeader>
								<div className="w-12 h-12 bg-purple-100 dark:bg-purple-950 rounded-lg flex items-center justify-center mb-3 group-hover:scale-110 transition-transform">
									<MessageSquare className="w-6 h-6 text-purple-600 dark:text-purple-400" />
								</div>
								<CardTitle className="text-lg">Start Chatting</CardTitle>
								<CardDescription>
									Jump right into the AI researcher and start asking questions
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2 text-sm text-muted-foreground">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>AI-powered conversations</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>Research and explore topics</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-green-600" />
										<span>Get instant insights</span>
									</div>
								</div>
								<Button
									className="w-full group-hover:bg-primary/90"
									onClick={() => router.push(`/dashboard/${searchSpaceId}/researcher`)}
								>
									Start Chatting
									<ArrowRight className="w-4 h-4 ml-2" />
								</Button>
							</CardContent>
						</Card>
					</motion.div>
				</div>

				{/* Quick Stats */}
				<motion.div
					initial={{ opacity: 0, y: 10 }}
					animate={{ opacity: 1, y: 0 }}
					transition={{ delay: 0.9 }}
					className="flex flex-wrap justify-center gap-2 pt-4"
				>
					<Badge variant="secondary">
						✓ {allConfigs.length} LLM provider{allConfigs.length > 1 ? "s" : ""} available
					</Badge>
					{globalConfigs.length > 0 && (
						<Badge variant="secondary">✓ {globalConfigs.length} Global config(s)</Badge>
					)}
					{llmConfigs.length > 0 && (
						<Badge variant="secondary">✓ {llmConfigs.length} Custom config(s)</Badge>
					)}
					<Badge variant="secondary">✓ All roles assigned</Badge>
					<Badge variant="secondary">✓ Ready to use</Badge>
				</motion.div>
			</motion.div>
		</div>
	);
}
