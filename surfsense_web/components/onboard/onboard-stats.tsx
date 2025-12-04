"use client";

import { Bot, Brain, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { Badge } from "@/components/ui/badge";

interface OnboardStatsProps {
	globalConfigsCount: number;
	userConfigsCount: number;
}

export function OnboardStats({ globalConfigsCount, userConfigsCount }: OnboardStatsProps) {
	return (
		<motion.div
			initial={{ opacity: 0, y: 20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ delay: 0.5 }}
			className="flex flex-wrap justify-center gap-3 mb-10"
		>
			{globalConfigsCount > 0 && (
				<Badge variant="secondary" className="px-3 py-1.5">
					<Sparkles className="w-3 h-3 mr-1.5 text-violet-500" />
					{globalConfigsCount} Global Model{globalConfigsCount > 1 ? "s" : ""}
				</Badge>
			)}
			{userConfigsCount > 0 && (
				<Badge variant="secondary" className="px-3 py-1.5">
					<Bot className="w-3 h-3 mr-1.5 text-blue-500" />
					{userConfigsCount} Custom Config{userConfigsCount > 1 ? "s" : ""}
				</Badge>
			)}
			<Badge variant="secondary" className="px-3 py-1.5">
				<Brain className="w-3 h-3 mr-1.5 text-fuchsia-500" />
				All Roles Assigned
			</Badge>
		</motion.div>
	);
}
