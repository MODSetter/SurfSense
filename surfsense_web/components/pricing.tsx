"use client";

import NumberFlow from "@number-flow/react";
import confetti from "canvas-confetti";
import { Check, Star } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useRef, useState } from "react";
import { buttonVariants } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useMediaQuery } from "@/hooks/use-media-query";
import { cn } from "@/lib/utils";

interface PricingPlan {
	name: string;
	price: string;
	yearlyPrice: string;
	period: string;
	features: string[];
	description: string;
	buttonText: string;
	href: string;
	isPopular: boolean;
}

interface PricingProps {
	plans: PricingPlan[];
	title?: string;
	description?: string;
}

export function Pricing({
	plans,
	title = "Simple, Transparent Pricing",
	description = "Choose the plan that works for you\nAll plans include access to our platform, lead generation tools, and dedicated support.",
}: PricingProps) {
	const [isMonthly, setIsMonthly] = useState(true);
	const isDesktop = useMediaQuery("(min-width: 768px)");
	const switchRef = useRef<HTMLButtonElement>(null);

	const handleToggle = (checked: boolean) => {
		setIsMonthly(!checked);
		if (checked && switchRef.current) {
			const rect = switchRef.current.getBoundingClientRect();
			const x = rect.left + rect.width / 2;
			const y = rect.top + rect.height / 2;

			confetti({
				particleCount: 50,
				spread: 60,
				origin: {
					x: x / window.innerWidth,
					y: y / window.innerHeight,
				},
				colors: [
					"hsl(var(--primary))",
					"hsl(var(--accent))",
					"hsl(var(--secondary))",
					"hsl(var(--muted))",
				],
				ticks: 200,
				gravity: 1.2,
				decay: 0.94,
				startVelocity: 30,
				shapes: ["circle"],
			});
		}
	};

	return (
		<div className="container py-20">
			<div className="text-center space-y-4 mb-12">
				<h2 className="text-4xl font-bold tracking-tight sm:text-5xl">{title}</h2>
				<p className="text-muted-foreground text-lg whitespace-pre-line">{description}</p>
			</div>

			{/* <div className="flex justify-center mb-10">
				<label
					htmlFor="billing-toggle"
					className="relative inline-flex items-center cursor-pointer"
				>
					<Label>
						<Switch
							ref={switchRef as any}
							checked={!isMonthly}
							onCheckedChange={handleToggle}
							className="relative"
						/>
					</Label>
				</label>
				<span className="ml-2 font-semibold">
					Annual billing <span className="text-primary">(Save 20%)</span>
				</span>
			</div> */}

			<div
				className={cn(
					"grid grid-cols-1 gap-4",
					plans.length === 2 ? "md:grid-cols-2 max-w-5xl mx-auto" : "md:grid-cols-3"
				)}
			>
				{plans.map((plan, index) => (
					<motion.div
						key={index}
						initial={{ y: 50, opacity: 1 }}
						whileInView={
							isDesktop
								? plans.length === 2
									? {
											y: plan.isPopular ? -20 : 0,
											opacity: 1,
											scale: plan.isPopular ? 1.0 : 0.96,
										}
									: {
											y: plan.isPopular ? -20 : 0,
											opacity: 1,
											x: index === 2 ? -30 : index === 0 ? 30 : 0,
											scale: index === 0 || index === 2 ? 0.94 : 1.0,
										}
								: {}
						}
						viewport={{ once: true }}
						transition={{
							duration: 1.6,
							type: "spring",
							stiffness: 100,
							damping: 30,
							delay: 0.4,
							opacity: { duration: 0.5 },
						}}
						className={cn(
							`rounded-2xl border-[1px] p-6 bg-background text-center lg:flex lg:flex-col lg:justify-center relative`,
							plan.isPopular ? "border-primary border-2" : "border-border",
							"flex flex-col",
							!plan.isPopular && "mt-5",
							plans.length === 3 && (index === 0 || index === 2)
								? "z-0 transform translate-x-0 translate-y-0 -translate-z-[50px] rotate-y-[10deg]"
								: plans.length === 2 && !plan.isPopular
									? "z-0"
									: "z-10",
							plans.length === 3 && index === 0 && "origin-right",
							plans.length === 3 && index === 2 && "origin-left"
						)}
					>
						{plan.isPopular && (
							<div className="absolute top-0 right-0 bg-primary py-0.5 px-2 rounded-bl-xl rounded-tr-xl flex items-center">
								<Star className="text-primary-foreground h-4 w-4 fill-current" />
								<span className="text-primary-foreground ml-1 font-sans font-semibold">
									Popular
								</span>
							</div>
						)}
						<div className="flex-1 flex flex-col">
							<p className="text-base font-semibold text-muted-foreground">{plan.name}</p>
							<div className="mt-6 flex items-center justify-center gap-x-2">
								<span className="text-5xl font-bold tracking-tight text-foreground">
									{isNaN(Number(plan.price)) ? (
										<span>{isMonthly ? plan.price : plan.yearlyPrice}</span>
									) : (
										<NumberFlow
											value={isMonthly ? Number(plan.price) : Number(plan.yearlyPrice)}
											format={{
												style: "currency",
												currency: "USD",
												minimumFractionDigits: 0,
												maximumFractionDigits: 0,
											}}
											transformTiming={{
												duration: 500,
												easing: "ease-out",
											}}
											willChange
											className="font-variant-numeric: tabular-nums"
										/>
									)}
								</span>
								{plan.period && plan.period !== "Next 3 months" && (
									<span className="text-sm font-semibold leading-6 tracking-wide text-muted-foreground">
										/ {plan.period}
									</span>
								)}
							</div>

							<p className="text-xs leading-5 text-muted-foreground">
								{isNaN(Number(plan.price)) ? "" : isMonthly ? "billed monthly" : "billed annually"}
							</p>

							<ul className="mt-5 gap-2 flex flex-col">
								{plan.features.map((feature, idx) => (
									<li key={idx} className="flex items-start gap-2">
										<Check className="h-4 w-4 text-primary mt-1 flex-shrink-0" />
										<span className="text-left">{feature}</span>
									</li>
								))}
							</ul>

							<hr className="w-full my-4" />

							<Link
								href={plan.href}
								className={cn(
									buttonVariants({
										variant: "outline",
									}),
									"group relative w-full gap-2 overflow-hidden text-lg font-semibold tracking-tighter",
									"transform-gpu ring-offset-current transition-all duration-300 ease-out hover:ring-2 hover:ring-primary hover:ring-offset-1 hover:bg-primary hover:text-primary-foreground",
									plan.isPopular
										? "bg-primary text-primary-foreground"
										: "bg-background text-foreground"
								)}
							>
								{plan.buttonText}
							</Link>
							<p className="mt-6 text-xs leading-5 text-muted-foreground">{plan.description}</p>
						</div>
					</motion.div>
				))}
			</div>
		</div>
	);
}
