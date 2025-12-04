"use client";

import { ArrowRight, CheckCircle, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface OnboardActionCardProps {
	title: string;
	description: string;
	icon: LucideIcon;
	features: string[];
	buttonText: string;
	onClick: () => void;
	colorScheme: "emerald" | "blue" | "violet";
	delay?: number;
}

const colorSchemes = {
	emerald: {
		iconBg: "bg-emerald-500/10 dark:bg-emerald-500/20",
		iconRing: "ring-emerald-500/20 dark:ring-emerald-500/30",
		iconColor: "text-emerald-600 dark:text-emerald-400",
		checkColor: "text-emerald-500",
		buttonBg: "bg-emerald-600 hover:bg-emerald-500",
		hoverBorder: "hover:border-emerald-500/50",
	},
	blue: {
		iconBg: "bg-blue-500/10 dark:bg-blue-500/20",
		iconRing: "ring-blue-500/20 dark:ring-blue-500/30",
		iconColor: "text-blue-600 dark:text-blue-400",
		checkColor: "text-blue-500",
		buttonBg: "bg-blue-600 hover:bg-blue-500",
		hoverBorder: "hover:border-blue-500/50",
	},
	violet: {
		iconBg: "bg-violet-500/10 dark:bg-violet-500/20",
		iconRing: "ring-violet-500/20 dark:ring-violet-500/30",
		iconColor: "text-violet-600 dark:text-violet-400",
		checkColor: "text-violet-500",
		buttonBg: "bg-violet-600 hover:bg-violet-500",
		hoverBorder: "hover:border-violet-500/50",
	},
};

export function OnboardActionCard({
	title,
	description,
	icon: Icon,
	features,
	buttonText,
	onClick,
	colorScheme,
	delay = 0,
}: OnboardActionCardProps) {
	const colors = colorSchemes[colorScheme];

	return (
		<motion.div
			initial={{ opacity: 0, y: 30 }}
			animate={{ opacity: 1, y: 0 }}
			transition={{ delay, type: "spring", stiffness: 200 }}
			whileHover={{ y: -6, transition: { duration: 0.2 } }}
		>
			<Card
				className={cn(
					"h-full cursor-pointer group relative overflow-hidden transition-all duration-300",
					"border bg-card hover:shadow-lg",
					colors.hoverBorder
				)}
				onClick={onClick}
			>
				<CardHeader className="relative pb-4">
					<motion.div
						className={cn(
							"w-14 h-14 rounded-2xl flex items-center justify-center mb-4 ring-1 transition-all duration-300",
							colors.iconBg,
							colors.iconRing,
							"group-hover:scale-110"
						)}
						whileHover={{ rotate: [0, -5, 5, 0] }}
						transition={{ duration: 0.5 }}
					>
						<Icon className={cn("w-7 h-7", colors.iconColor)} />
					</motion.div>
					<CardTitle className="text-xl">{title}</CardTitle>
					<CardDescription>{description}</CardDescription>
				</CardHeader>

				<CardContent className="relative space-y-4">
					<div className="space-y-2.5 text-sm text-muted-foreground">
						{features.map((feature, index) => (
							<div key={index} className="flex items-center gap-2.5">
								<CheckCircle className={cn("w-4 h-4", colors.checkColor)} />
								<span>{feature}</span>
							</div>
						))}
					</div>

					<Button
						className={cn(
							"w-full text-white border-0 transition-all duration-300",
							colors.buttonBg
						)}
					>
						{buttonText}
						<ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-1 transition-transform" />
					</Button>
				</CardContent>
			</Card>
		</motion.div>
	);
}
