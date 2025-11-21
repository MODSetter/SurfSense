"use client";

import { Brain, Loader2, Sparkles } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import type { LLMConfig } from "@/hooks/use-llm-configs";

interface ModelStatusIndicatorProps {
	/** Current LLM configuration being used */
	currentModel?: LLMConfig | null;
	/** Whether the model is currently streaming a response */
	isStreaming?: boolean;
	/** Whether the model is processing/thinking */
	isThinking?: boolean;
	/** Whether to show in collapsed mode */
	collapsed?: boolean;
}

/**
 * ModelStatusIndicator displays the current AI model status in the sidebar
 * Similar to Claude.ai's model indicator, showing:
 * - Current model name and provider
 * - Activity status (streaming, thinking, idle)
 * - Animated indicator during activity
 */
export function ModelStatusIndicator({
	currentModel,
	isStreaming = false,
	isThinking = false,
	collapsed = false,
}: ModelStatusIndicatorProps) {
	// Determine current status
	const status = useMemo(() => {
		if (isStreaming) return "streaming";
		if (isThinking) return "thinking";
		return "idle";
	}, [isStreaming, isThinking]);

	// Format model display name
	const displayName = useMemo(() => {
		if (!currentModel) return "No Model";

		// For Gemini models, show a cleaner name
		if (currentModel.provider === "gemini" || currentModel.provider === "google") {
			return currentModel.model_name
				.replace("models/", "")
				.replace("gemini-", "Gemini ")
				.replace("-exp", " Exp")
				.replace("2.0", "2.0")
				.replace("flash", "Flash");
		}

		// For other models, show provider + model
		return `${currentModel.provider} / ${currentModel.model_name}`;
	}, [currentModel]);

	// Status colors and icons
	const statusConfig = useMemo(() => {
		switch (status) {
			case "streaming":
				return {
					color: "text-blue-500",
					bgColor: "bg-blue-500/10",
					label: "Responding",
					icon: Sparkles,
				};
			case "thinking":
				return {
					color: "text-amber-500",
					bgColor: "bg-amber-500/10",
					label: "Thinking",
					icon: Loader2,
				};
			default:
				return {
					color: "text-muted-foreground",
					bgColor: "bg-muted",
					label: "Ready",
					icon: Brain,
				};
		}
	}, [status]);

	const StatusIcon = statusConfig.icon;

	if (collapsed) {
		return (
			<TooltipProvider>
				<Tooltip>
					<TooltipTrigger asChild>
						<div className="flex items-center justify-center p-2 rounded-md hover:bg-accent/50 transition-colors">
							<div className="relative">
								<StatusIcon
									className={`h-4 w-4 ${statusConfig.color} ${status !== "idle" ? "animate-pulse" : ""}`}
								/>
								{status !== "idle" && (
									<motion.div
										className={`absolute inset-0 rounded-full ${statusConfig.bgColor}`}
										initial={{ scale: 1, opacity: 0.5 }}
										animate={{ scale: 1.5, opacity: 0 }}
										transition={{ duration: 1.5, repeat: Number.POSITIVE_INFINITY }}
									/>
								)}
							</div>
						</div>
					</TooltipTrigger>
					<TooltipContent side="right" className="max-w-[200px]">
						<div className="text-xs space-y-1">
							<p className="font-medium">{displayName}</p>
							<p className="text-muted-foreground">{statusConfig.label}</p>
						</div>
					</TooltipContent>
				</Tooltip>
			</TooltipProvider>
		);
	}

	return (
		<div className="px-3 py-2 rounded-lg border bg-card/50 hover:bg-accent/30 transition-all group">
			<div className="flex items-center gap-2">
				{/* Status Icon with Animation */}
				<div className="relative flex-shrink-0">
					<StatusIcon
						className={`h-4 w-4 ${statusConfig.color} ${status === "thinking" ? "animate-spin" : status === "streaming" ? "animate-pulse" : ""}`}
					/>
					<AnimatePresence>
						{status !== "idle" && (
							<motion.div
								className={`absolute inset-0 rounded-full ${statusConfig.bgColor}`}
								initial={{ scale: 1, opacity: 0.5 }}
								animate={{ scale: 2, opacity: 0 }}
								exit={{ scale: 1, opacity: 0 }}
								transition={{
									duration: 1.5,
									repeat: Number.POSITIVE_INFINITY,
									ease: "easeOut"
								}}
							/>
						)}
					</AnimatePresence>
				</div>

				{/* Model Info */}
				<div className="flex-1 min-w-0">
					<div className="flex items-center gap-2">
						<p className="text-xs font-medium truncate">
							{displayName}
						</p>
						{status !== "idle" && (
							<Badge
								variant="secondary"
								className={`h-5 px-1.5 text-[10px] ${statusConfig.bgColor} ${statusConfig.color} border-none`}
							>
								{statusConfig.label}
							</Badge>
						)}
					</div>
					{currentModel && (
						<p className="text-[10px] text-muted-foreground truncate">
							{currentModel.provider}
						</p>
					)}
				</div>
			</div>
		</div>
	);
}
