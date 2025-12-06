"use client";

import { Wand2 } from "lucide-react";
import { motion } from "motion/react";

interface OnboardLoadingProps {
	title: string;
	subtitle: string;
}

export function OnboardLoading({ title, subtitle }: OnboardLoadingProps) {
	return (
		<div className="min-h-screen bg-background flex items-center justify-center p-4">
			<motion.div
				initial={{ opacity: 0, scale: 0.9 }}
				animate={{ opacity: 1, scale: 1 }}
				transition={{ duration: 0.5 }}
				className="text-center"
			>
				<div className="relative mb-8 flex justify-center">
					<motion.div
						animate={{ rotate: 360 }}
						transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
					>
						<Wand2 className="w-16 h-16 text-primary" />
					</motion.div>
				</div>
				<h2 className="text-2xl font-bold text-foreground mb-2">{title}</h2>
				<p className="text-muted-foreground">{subtitle}</p>
				<div className="mt-6 flex justify-center gap-1.5">
					{[0, 1, 2].map((i) => (
						<motion.div
							key={i}
							className="w-2 h-2 rounded-full bg-primary"
							animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
							transition={{
								duration: 1,
								repeat: Infinity,
								delay: i * 0.2,
							}}
						/>
					))}
				</div>
			</motion.div>
		</div>
	);
}
