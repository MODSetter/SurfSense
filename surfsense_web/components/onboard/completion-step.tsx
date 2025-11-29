"use client";

import {
	ArrowRight,
	Bot,
	Brain,
	CheckCircle,
	FileText,
	MessageSquare,
	Sparkles,
	UserPlus,
	Users,
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

				<div className="grid grid-cols-1 md:grid-cols-3 gap-6">
					{/* Manage Team Card */}
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: 0.9, type: "spring", stiffness: 300, damping: 25 }}
					>
						<Card className="h-full border-2 hover:border-emerald-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-emerald-500/10 cursor-pointer group relative overflow-hidden">
							<div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500" />
							<CardHeader className="relative">
								<div className="w-12 h-12 bg-gradient-to-br from-emerald-500/20 to-emerald-600/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300 ring-1 ring-emerald-500/20">
									<Users className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
								</div>
								<CardTitle className="text-lg">Manage Team</CardTitle>
								<CardDescription>
									Invite team members and collaborate on your search space
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4 relative">
								<div className="space-y-2 text-sm text-muted-foreground">
									<div className="flex items-center gap-2">
										<UserPlus className="w-4 h-4 text-emerald-500" />
										<span>Invite team members</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Assign roles & permissions</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Collaborate together</span>
									</div>
								</div>
								<Button
									className="w-full bg-emerald-600 hover:bg-emerald-700 text-white group-hover:shadow-lg group-hover:shadow-emerald-500/25 transition-all duration-300"
									onClick={() => router.push(`/dashboard/${searchSpaceId}/team`)}
								>
									Manage Team
									<ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
								</Button>
							</CardContent>
						</Card>
					</motion.div>

					{/* Add Sources Card */}
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: 0.7, type: "spring", stiffness: 300, damping: 25 }}
					>
						<Card className="h-full border-2 hover:border-blue-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-blue-500/10 cursor-pointer group relative overflow-hidden">
							<div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-500/10 to-transparent rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500" />
							<CardHeader className="relative">
								<div className="w-12 h-12 bg-gradient-to-br from-blue-500/20 to-blue-600/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300 ring-1 ring-blue-500/20">
									<FileText className="w-6 h-6 text-blue-600 dark:text-blue-400" />
								</div>
								<CardTitle className="text-lg">Add Sources</CardTitle>
								<CardDescription>
									Connect your data sources to start building your knowledge base
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4 relative">
								<div className="space-y-2 text-sm text-muted-foreground">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Connect documents and files</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Import from various sources</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Build your knowledge base</span>
									</div>
								</div>
								<Button
									className="w-full bg-blue-600 hover:bg-blue-700 text-white group-hover:shadow-lg group-hover:shadow-blue-500/25 transition-all duration-300"
									onClick={() => router.push(`/dashboard/${searchSpaceId}/sources/add`)}
								>
									Add Sources
									<ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
								</Button>
							</CardContent>
						</Card>
					</motion.div>

					{/* Start Chatting Card */}
					<motion.div
						initial={{ opacity: 0, y: 20 }}
						animate={{ opacity: 1, y: 0 }}
						transition={{ delay: 0.8, type: "spring", stiffness: 300, damping: 25 }}
					>
						<Card className="h-full border-2 hover:border-purple-500/50 transition-all duration-300 hover:shadow-xl hover:shadow-purple-500/10 cursor-pointer group relative overflow-hidden">
							<div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-purple-500/10 to-transparent rounded-full blur-2xl -mr-16 -mt-16 group-hover:scale-150 transition-transform duration-500" />
							<CardHeader className="relative">
								<div className="w-12 h-12 bg-gradient-to-br from-purple-500/20 to-purple-600/10 rounded-xl flex items-center justify-center mb-3 group-hover:scale-110 group-hover:rotate-3 transition-all duration-300 ring-1 ring-purple-500/20">
									<MessageSquare className="w-6 h-6 text-purple-600 dark:text-purple-400" />
								</div>
								<CardTitle className="text-lg">Start Chatting</CardTitle>
								<CardDescription>
									Jump right into the AI researcher and start asking questions
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4 relative">
								<div className="space-y-2 text-sm text-muted-foreground">
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>AI-powered conversations</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Research and explore topics</span>
									</div>
									<div className="flex items-center gap-2">
										<CheckCircle className="w-4 h-4 text-emerald-500" />
										<span>Get instant insights</span>
									</div>
								</div>
								<Button
									className="w-full bg-purple-600 hover:bg-purple-700 text-white group-hover:shadow-lg group-hover:shadow-purple-500/25 transition-all duration-300"
									onClick={() => router.push(`/dashboard/${searchSpaceId}/researcher`)}
								>
									Start Chatting
									<ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
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
