"use client";

import { CheckCircle } from "lucide-react";
import { motion } from "motion/react";
import { Logo } from "@/components/Logo";
import { Badge } from "@/components/ui/badge";

interface OnboardHeaderProps {
	title: string;
	subtitle: string;
	isReady?: boolean;
}

export function OnboardHeader({ title, subtitle, isReady }: OnboardHeaderProps) {
	return (
		<motion.div
			initial={{ opacity: 0, y: -20 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ duration: 0.5, delay: 0.1 }}
			className="text-center mb-10"
		>
			<motion.div
				initial={{ scale: 0 }}
				animate={{ scale: 1 }}
				transition={{ type: "spring", stiffness: 200, delay: 0.2 }}
				className="inline-flex items-center justify-center mb-6"
			>
				<Logo className="w-20 h-20 rounded-2xl shadow-lg" />
			</motion.div>

			<motion.div
				initial={{ opacity: 0, y: 10 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ delay: 0.3 }}
				className="space-y-2"
			>
				<h1 className="text-4xl md:text-5xl font-bold text-foreground">{title}</h1>
				<p className="text-muted-foreground text-lg md:text-xl max-w-2xl mx-auto">{subtitle}</p>
			</motion.div>

			{isReady && (
				<motion.div
					initial={{ opacity: 0, scale: 0.8 }}
					animate={{ opacity: 1, scale: 1 }}
					transition={{ delay: 0.4, type: "spring" }}
					className="mt-4"
				>
					<Badge className="px-4 py-2 text-sm bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400">
						<CheckCircle className="w-4 h-4 mr-2" />
						AI Configuration Complete
					</Badge>
				</motion.div>
			)}
		</motion.div>
	);
}
