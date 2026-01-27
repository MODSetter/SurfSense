"use client";

import { IconCalendar, IconMailFilled } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Gift, Loader2, Mail, Star } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import type { IncentiveTaskInfo } from "@/contracts/types/incentive-tasks.types";
import { incentiveTasksApiService } from "@/lib/apis/incentive-tasks-api.service";
import {
	trackIncentiveContactOpened,
	trackIncentivePageViewed,
	trackIncentiveTaskClicked,
	trackIncentiveTaskCompleted,
} from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

export default function MorePagesPage() {
	const queryClient = useQueryClient();

	// Track page view on mount
	useEffect(() => {
		trackIncentivePageViewed();
	}, []);

	// Fetch tasks from API
	const { data, isLoading } = useQuery({
		queryKey: ["incentive-tasks"],
		queryFn: () => incentiveTasksApiService.getTasks(),
	});

	// Mutation to complete a task
	const completeMutation = useMutation({
		mutationFn: incentiveTasksApiService.completeTask,
		onSuccess: (response, taskType) => {
			if (response.success) {
				toast.success(response.message);
				// Track task completion
				const task = data?.tasks.find((t) => t.task_type === taskType);
				if (task) {
					trackIncentiveTaskCompleted(taskType, task.pages_reward);
				}
				// Invalidate queries to refresh data
				queryClient.invalidateQueries({ queryKey: ["incentive-tasks"] });
				queryClient.invalidateQueries({ queryKey: ["user"] });
			}
		},
		onError: () => {
			toast.error("Failed to complete task. Please try again.");
		},
	});

	const handleTaskClick = (task: IncentiveTaskInfo) => {
		if (!task.completed) {
			trackIncentiveTaskClicked(task.task_type);
			completeMutation.mutate(task.task_type);
		}
	};

	const allCompleted = data?.tasks.every((t) => t.completed) ?? false;

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
					<h2 className="text-xl font-bold tracking-tight">Get More Pages</h2>
					<p className="text-sm text-muted-foreground">Complete tasks to earn additional pages</p>
				</div>

				{/* Tasks */}
				{isLoading ? (
					<Card>
						<CardContent className="flex items-center gap-3 p-3">
							<Skeleton className="h-9 w-9 rounded-full" />
							<div className="flex-1 space-y-2">
								<Skeleton className="h-4 w-3/4" />
								<Skeleton className="h-3 w-1/4" />
							</div>
							<Skeleton className="h-8 w-16" />
						</CardContent>
					</Card>
				) : (
					<div className="space-y-2">
						{data?.tasks.map((task) => (
							<Card
								key={task.task_type}
								className={cn("transition-colors", task.completed && "bg-muted/50")}
							>
								<CardContent className="flex items-center gap-3 p-3">
									<div
										className={cn(
											"flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
											task.completed ? "bg-primary text-primary-foreground" : "bg-muted"
										)}
									>
										{task.completed ? <Check className="h-4 w-4" /> : <Star className="h-4 w-4" />}
									</div>
									<div className="flex-1 min-w-0">
										<p
											className={cn(
												"text-sm font-medium",
												task.completed && "text-muted-foreground line-through"
											)}
										>
											{task.title}
										</p>
										<p className="text-xs text-muted-foreground">+{task.pages_reward} pages</p>
									</div>
									<Button
										variant={task.completed ? "ghost" : "outline"}
										size="sm"
										disabled={task.completed || completeMutation.isPending}
										onClick={() => handleTaskClick(task)}
										asChild={!task.completed}
									>
										{task.completed ? (
											<span>Done</span>
										) : (
											<a
												href={task.action_url}
												target="_blank"
												rel="noopener noreferrer"
												className="gap-1"
											>
												{completeMutation.isPending ? (
													<Loader2 className="h-3 w-3 animate-spin" />
												) : (
													<>
														Go
														<ExternalLink className="h-3 w-3" />
													</>
												)}
											</a>
										)}
									</Button>
								</CardContent>
							</Card>
						))}
					</div>
				)}

				{/* Contact */}
				<Separator className="my-6" />
				<div className="text-center">
					<p className="mb-3 text-sm text-muted-foreground">
						{allCompleted ? "Thanks! Need even more pages?" : "Need more pages?"}
					</p>
					<Dialog onOpenChange={(open) => open && trackIncentiveContactOpened()}>
						<DialogTrigger asChild>
							<Button variant="outline" size="sm" className="gap-2">
								<Mail className="h-4 w-4" />
								Contact Us
							</Button>
						</DialogTrigger>
						<DialogContent className="sm:max-w-md">
							<DialogHeader>
								<DialogTitle>Contact Us</DialogTitle>
								<DialogDescription>Schedule a meeting or send us an email.</DialogDescription>
							</DialogHeader>
							<div className="flex flex-col items-center gap-4 py-4">
								<Link
									href="https://calendly.com/eric-surfsense/surfsense-meeting"
									target="_blank"
									rel="noopener noreferrer"
									className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:bg-primary/90"
								>
									<IconCalendar className="h-4 w-4" />
									Schedule a Meeting
								</Link>
								<div className="flex items-center gap-2 text-muted-foreground">
									<span className="h-px w-8 bg-border" />
									<span className="text-xs">or</span>
									<span className="h-px w-8 bg-border" />
								</div>
								<Link
									href="mailto:eric@surfsense.com"
									className="flex items-center gap-2 text-sm text-muted-foreground transition hover:text-foreground"
								>
									<IconMailFilled className="h-4 w-4" />
									eric@surfsense.com
								</Link>
							</div>
						</DialogContent>
					</Dialog>
				</div>
			</motion.div>
		</div>
	);
}
