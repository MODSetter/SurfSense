"use client";

import { IconCalendar, IconMailFilled } from "@tabler/icons-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Gift, Mail, Star, Zap } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
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
import { Spinner } from "@/components/ui/spinner";
import type { IncentiveTaskInfo } from "@/contracts/types/incentive-tasks.types";
import { incentiveTasksApiService } from "@/lib/apis/incentive-tasks-api.service";
import {
	trackIncentiveContactOpened,
	trackIncentivePageViewed,
	trackIncentiveTaskClicked,
	trackIncentiveTaskCompleted,
} from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

export function MorePagesContent() {
	const queryClient = useQueryClient();

	useEffect(() => {
		trackIncentivePageViewed();
	}, []);

	const { data, isLoading } = useQuery({
		queryKey: ["incentive-tasks"],
		queryFn: () => incentiveTasksApiService.getTasks(),
	});

	const completeMutation = useMutation({
		mutationFn: incentiveTasksApiService.completeTask,
		onSuccess: (response, taskType) => {
			if (response.success) {
				toast.success(response.message);
				const task = data?.tasks.find((t) => t.task_type === taskType);
				if (task) {
					trackIncentiveTaskCompleted(taskType, task.pages_reward);
				}
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

	return (
		<div className="w-full space-y-6">
			<div className="text-center">
				<Gift className="mx-auto mb-3 h-8 w-8 text-primary" />
				<h2 className="text-xl font-bold tracking-tight">Get More Pages</h2>
				<p className="mt-1 text-sm text-muted-foreground">
					Complete tasks to earn additional pages
				</p>
			</div>

			{isLoading ? (
			<Card>
				<CardContent className="flex items-center gap-3 p-3">
					<Skeleton className="h-9 w-9 rounded-full bg-muted" />
					<div className="flex-1 space-y-2">
						<Skeleton className="h-4 w-3/4 bg-muted" />
						<Skeleton className="h-3 w-1/4 bg-muted" />
					</div>
					<Skeleton className="h-8 w-16 bg-muted" />
				</CardContent>
			</Card>
			) : (
				<div className="space-y-2">
					{data?.tasks.map((task) => (
						<Card
							key={task.task_type}
							className={cn("transition-colors bg-transparent", task.completed && "bg-muted/50")}
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
								<div className="min-w-0 flex-1">
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
								variant="ghost"
								size="sm"
								disabled={task.completed || completeMutation.isPending}
								onClick={() => handleTaskClick(task)}
								asChild={!task.completed}
								className="text-muted-foreground hover:text-foreground"
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
												<Spinner size="xs" />
											) : (
												<ExternalLink className="h-3 w-3" />
											)}
										</a>
									)}
								</Button>
							</CardContent>
						</Card>
					))}
				</div>
			)}

			<Separator />

			<Card className="overflow-hidden border-emerald-500/20 bg-transparent">
				<CardHeader className="pb-2">
					<div className="flex items-center gap-2">
						<Zap className="h-4 w-4 text-emerald-500" />
						<CardTitle className="text-base">Upgrade to PRO</CardTitle>
						<Badge className="bg-emerald-600 text-white border-transparent hover:bg-emerald-600">
							FREE
						</Badge>
					</div>
					<CardDescription>
						For a limited time, get{" "}
						<span className="font-semibold text-foreground">6,000 additional pages</span> at no
						cost. Contact us and we&apos;ll upgrade your account instantly.
					</CardDescription>
				</CardHeader>
				<CardFooter className="pt-2">
					<Dialog onOpenChange={(open) => open && trackIncentiveContactOpened()}>
						<DialogTrigger asChild>
							<Button className="w-full bg-emerald-600 text-white hover:bg-emerald-700">
								<Mail className="h-4 w-4" />
								Contact Us to Upgrade
							</Button>
						</DialogTrigger>
						<DialogContent className="select-none sm:max-w-sm">
							<DialogHeader>
								<DialogTitle>Get in Touch</DialogTitle>
								<DialogDescription>Pick the option that works best for you.</DialogDescription>
							</DialogHeader>
							<div className="flex flex-col gap-2">
								<Button asChild>
									<Link
										href="https://cal.com/mod-rohan"
										target="_blank"
										rel="noopener noreferrer"
									>
										<IconCalendar className="h-4 w-4" />
										Schedule a Meeting
									</Link>
								</Button>
								<Button variant="outline" asChild>
									<Link href="mailto:rohan@surfsense.com">
										<IconMailFilled className="h-4 w-4" />
										rohan@surfsense.com
									</Link>
								</Button>
							</div>
						</DialogContent>
					</Dialog>
				</CardFooter>
			</Card>
		</div>
	);
}
