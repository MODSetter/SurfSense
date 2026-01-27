"use client";

import { ExternalLink, Gift, Mail, Star, MessageSquarePlus, Share2, Check } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

const GITHUB_REPO_URL = "https://github.com/MODSetter/SurfSense";

const INITIAL_TASKS = [
	{
		id: "star",
		title: "Star the repository",
		reward: 100,
		href: GITHUB_REPO_URL,
		icon: Star,
	},
	{
		id: "issue",
		title: "Create an issue",
		reward: 50,
		href: `${GITHUB_REPO_URL}/issues/new/choose`,
		icon: MessageSquarePlus,
	},
	{
		id: "share",
		title: "Share on social media",
		reward: 50,
		href: `https://twitter.com/intent/tweet?text=Check out SurfSense - an AI-powered personal knowledge base!&url=${encodeURIComponent(GITHUB_REPO_URL)}`,
		icon: Share2,
	},
] as const;

export default function FreePagesPage() {
	const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

	const handleTaskClick = useCallback((taskId: string) => {
		setCompletedIds((prev) => new Set(prev).add(taskId));
	}, []);

	const allCompleted = completedIds.size === INITIAL_TASKS.length;

	return (
		<div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4 py-8">
			<motion.div
				initial={{ opacity: 0, y: 20 }}
				animate={{ opacity: 1, y: 0 }}
				transition={{ duration: 0.3 }}
				className="w-full max-w-md"
			>
				{/* Header */}
				<div className="mb-6 text-center">
					<Gift className="mx-auto mb-3 h-8 w-8 text-primary" />
					<h2 className="text-xl font-bold tracking-tight">Get Pages</h2>
					<p className="text-sm text-muted-foreground">
						Complete tasks to get free additional pages
					</p>
				</div>

				{/* Tasks */}
				<div className="space-y-2">
					{INITIAL_TASKS.map((task) => {
						const isCompleted = completedIds.has(task.id);
						const Icon = task.icon;
						return (
							<Card
								key={task.id}
								className={cn("transition-colors", isCompleted && "bg-muted/50")}
							>
								<CardContent className="flex items-center gap-3 p-3">
									<div
										className={cn(
											"flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
											isCompleted ? "bg-primary text-primary-foreground" : "bg-muted"
										)}
									>
										{isCompleted ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
									</div>
									<div className="flex-1 min-w-0">
										<p className={cn("text-sm font-medium", isCompleted && "text-muted-foreground line-through")}>
											{task.title}
										</p>
										<p className="text-xs text-muted-foreground">+{task.reward} pages</p>
									</div>
									<Button
										variant={isCompleted ? "ghost" : "outline"}
										size="sm"
										asChild
										onClick={() => handleTaskClick(task.id)}
									>
										<a
											href={task.href}
											target="_blank"
											rel="noopener noreferrer"
											className={cn("gap-1", isCompleted && "pointer-events-none opacity-50")}
										>
											{isCompleted ? "Done" : "Go"}
											{!isCompleted && <ExternalLink className="h-3 w-3" />}
										</a>
									</Button>
								</CardContent>
							</Card>
						);
					})}
				</div>

				{/* Contact */}
				<Separator className="my-6" />
				<div className="text-center">
					<p className="mb-3 text-sm text-muted-foreground">
						{allCompleted ? "All done! Need more?" : "Need more pages?"}
					</p>
					<Button variant="outline" size="sm" asChild>
						<Link href="mailto:rohan@surfsense.com?subject=Request%20to%20Increase%20Page%20Limits" className="gap-2">
							<Mail className="h-4 w-4" />
							Contact Us
						</Link>
					</Button>
				</div>
			</motion.div>
		</div>
	);
}
