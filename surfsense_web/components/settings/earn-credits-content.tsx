"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { USER_QUERY_KEY } from "@/atoms/user/user-query.atoms";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import type { IncentiveTaskInfo } from "@/contracts/types/incentive-tasks.types";
import { incentiveTasksApiService } from "@/lib/apis/incentive-tasks-api.service";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { trackIncentiveTaskClicked } from "@/lib/posthog/events";
import { getWorkspaceIdParam } from "@/lib/route-params";
import { cn } from "@/lib/utils";

// Compact dollar label for a task's reward (e.g. "+$0.03").
const formatRewardUsd = (micros: number) => {
	const dollars = micros / 1_000_000;
	if (dollars >= 1) return `+$${dollars.toFixed(2)}`;
	return `+$${dollars.toFixed(2)}`;
};

export function EarnCreditsContent() {
	const params = useParams();
	const queryClient = useQueryClient();
	const workspaceId = getWorkspaceIdParam(params) ?? "";

	// incentive_page_viewed removed — redundant with $pageview.

	const { data, isLoading } = useQuery({
		queryKey: ["incentive-tasks"],
		queryFn: () => incentiveTasksApiService.getTasks(),
	});
	const { data: creditStatus } = useQuery({
		queryKey: ["credit-status"],
		queryFn: () => stripeApiService.getCreditStatus(),
	});
	const creditBuyingEnabled = creditStatus?.credit_buying_enabled ?? true;

	const completeMutation = useMutation({
		mutationFn: incentiveTasksApiService.completeTask,
		onSuccess: (response) => {
			if (response.success) {
				toast.success(response.message);
				// incentive_task_completed is now emitted server-side
				// (incentive_tasks_routes.complete_task) where credit is granted.
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
				<h2 className="text-xl font-bold tracking-tight">Earn Credits</h2>
				<p className="mt-1 text-sm text-muted-foreground">Earn bonus credits by completing tasks</p>
			</div>

			<div className="space-y-2">
				<h3 className="text-sm font-semibold">Earn Bonus Credits</h3>
				{isLoading ? (
					<div className="space-y-1.5">
						{["github", "reddit", "discord"].map((task) => (
							<Card key={task} className="bg-transparent">
								<CardContent className="flex items-center gap-3 p-3">
									<Skeleton className="h-8 w-8 rounded-full bg-muted" />
									<Skeleton className="h-4 flex-1 bg-muted" />
									<Skeleton className="h-8 w-16 bg-muted" />
								</CardContent>
							</Card>
						))}
					</div>
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
											"flex h-9 min-w-9 shrink-0 items-center justify-center rounded-full px-2",
											task.completed ? "bg-primary text-primary-foreground" : "bg-muted"
										)}
									>
										{task.completed ? (
											<Check className="h-3.5 w-3.5" />
										) : (
											<span className="text-[11px] font-semibold tabular-nums">
												{formatRewardUsd(task.credit_micros_reward)}
											</span>
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
										className="text-muted-foreground hover:text-accent-foreground"
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

			<div className="text-center">
				<p className="text-sm text-muted-foreground">Need more?</p>
				{creditBuyingEnabled ? (
					<Button asChild variant="link" className="text-emerald-600 dark:text-emerald-400">
						<Link href={`/dashboard/${workspaceId}/buy-more`}>Buy credits at $1 per $1</Link>
					</Button>
				) : (
					<p className="text-xs text-muted-foreground">
						Credit purchases are temporarily unavailable.
					</p>
				)}
			</div>
		</div>
	);
}
