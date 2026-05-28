"use client";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeleton for the detail page. Mirrors the loaded view's main/sidebar
 * grid (Definition + Runs on the left, Triggers on the right) so layout
 * doesn't reflow when data arrives.
 */
export function AutomationDetailLoading() {
	return (
		<>
			<div className="space-y-3">
				<Skeleton className="h-4 w-32" />
				<div className="flex items-center gap-3">
					<Skeleton className="h-7 w-64" />
					<Skeleton className="h-5 w-16 rounded-md" />
				</div>
				<Skeleton className="h-4 w-96" />
			</div>

			<div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
				<div className="space-y-6 min-w-0 lg:col-span-2">
					<Card className="border-border/60 bg-accent">
						<CardHeader>
							<Skeleton className="h-5 w-32" />
						</CardHeader>
						<CardContent className="space-y-4">
							<Skeleton className="h-4 w-3/4" />
							<Skeleton className="h-4 w-1/2" />
							<Skeleton className="h-24 w-full" />
						</CardContent>
					</Card>
					<Card className="border-border/60 bg-accent">
						<CardHeader>
							<Skeleton className="h-5 w-32" />
						</CardHeader>
						<CardContent>
							<Skeleton className="h-20 w-full" />
						</CardContent>
					</Card>
				</div>
				<div className="space-y-6 min-w-0">
					<Card className="border-border/60 bg-accent">
						<CardHeader>
							<Skeleton className="h-5 w-24" />
						</CardHeader>
						<CardContent>
							<Skeleton className="h-20 w-full" />
						</CardContent>
					</Card>
				</div>
			</div>
		</>
	);
}
