"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Mail } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import type { IncentiveTaskInfo } from "@/contracts/types/incentive-tasks.types";
import { incentiveTasksApiService } from "@/lib/apis/incentive-tasks-api.service";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import {
	trackIncentivePageViewed,
	trackIncentiveTaskClicked,
	trackIncentiveTaskCompleted,
} from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

export function MorePagesContent() {
	const params = useParams();
	const queryClient = useQueryClient();
	const searchSpaceId = params?.search_space_id ?? "";
	const [claimOpen, setClaimOpen] = useState(false);

	useEffect(() => {
		trackIncentivePageViewed();
	}, []);

	const { data, isLoading } = useQuery({
		queryKey: ["incentive-tasks"],
		queryFn: () => incentiveTasksApiService.getTasks(),
	});
	const { data: stripeStatus } = useQuery({
		queryKey: ["stripe-status"],
		queryFn: () => stripeApiService.getStatus(),
	});
	const pageBuyingEnabled = stripeStatus?.page_buying_enabled ?? true;

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
				queryClient.invalidateQueries({ queryKey: USER_QUERY_KEY });
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
		<div className="w-full space-y-5">
			<div className="text-center">
				<h2 className="text-xl font-bold tracking-tight">Get Free Pages</h2>
				<p className="mt-1 text-sm text-muted-foreground">
					Claim your free page offer and earn bonus pages
				</p>
			</div>

			{/* 6k free offer */}
			<Card className="border-emerald-500/30 bg-emerald-500/5">
				<CardContent className="flex items-center gap-3 p-4">
					<div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white text-xs font-bold">
						6k
					</div>
					<div className="min-w-0 flex-1">
						<p className="text-sm font-semibold">Claim 6,000 Free Pages</p>
						<p className="text-xs text-muted-foreground">
							Limited offer. Schedule a meeting or email us to claim.
						</p>
					</div>
					<Button
						size="sm"
						className="bg-emerald-600 text-white hover:bg-emerald-700"
						onClick={() => setClaimOpen(true)}
					>
						Claim
					</Button>
				</CardContent>
			</Card>

			<Separator />

			{/* Free tasks */}
			<div className="space-y-2">
				<h3 className="text-sm font-semibold">Earn Bonus Pages</h3>
				{isLoading ? (
					<Card>
						<CardContent className="flex items-center gap-3 p-3">
							<Skeleton className="h-8 w-8 rounded-full bg-muted" />
							<div className="flex-1 space-y-2">
								<Skeleton className="h-4 w-3/4 bg-muted" />
							</div>
							<Skeleton className="h-8 w-16 bg-muted" />
						</CardContent>
					</Card>
				) : (
					<div className="space-y-1.5">
						{data?.tasks.map((task) => (
							<Card
								key={task.task_type}
								className={cn("transition-colors bg-transparent", task.completed && "bg-muted/50")}
							>
								<CardContent className="flex items-center gap-3 p-3">
									<div
										className={cn(
											"flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
											task.completed ? "bg-primary text-primary-foreground" : "bg-muted"
										)}
									>
										{task.completed ? (
											<Check className="h-3.5 w-3.5" />
										) : (
											<span className="text-xs font-semibold">+{task.pages_reward}</span>
										)}
									</div>
									<p
										className={cn(
											"min-w-0 flex-1 text-sm font-medium",
											task.completed && "text-muted-foreground line-through"
										)}
									>
										{task.title}
									</p>
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
			</div>

			<Separator />

			{/* Link to buy pages */}
			<div className="text-center">
				<p className="text-sm text-muted-foreground">Need more?</p>
				{pageBuyingEnabled ? (
					<Button asChild variant="link" className="text-emerald-600 dark:text-emerald-400">
						<Link href={`/dashboard/${searchSpaceId}/buy-pages`}>
							Buy page packs at $1 per 1,000
						</Link>
					</Button>
				) : (
					<p className="text-xs text-muted-foreground">
						Page purchases are temporarily unavailable.
					</p>
				)}
			</div>

			{/* Claim 6k dialog */}
			<Dialog open={claimOpen} onOpenChange={setClaimOpen}>
				<DialogContent className="sm:max-w-md">
					<DialogHeader>
						<DialogTitle>Claim 6,000 Free Pages</DialogTitle>
						<DialogDescription>
							Send us an email to claim your free 6,000 pages. Include your account email and
							primary usecase for free pages.
						</DialogDescription>
					</DialogHeader>
					<Button asChild className="w-full gap-2">
						<a href="mailto:rohan@surfsense.com?subject=Claim%206%2C000%20Free%20Pages&body=Hi%2C%20I'd%20like%20to%20claim%20the%206%2C000%20free%20pages%20offer.%0A%0AMy%20account%20email%3A%20">
							<Mail className="h-4 w-4" />
							rohan@surfsense.com
						</a>
					</Button>
				</DialogContent>
			</Dialog>
		</div>
	);
}
