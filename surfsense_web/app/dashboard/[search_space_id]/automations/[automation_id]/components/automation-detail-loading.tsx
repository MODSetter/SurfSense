"use client";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Skeleton for the detail page. Same shell as the loaded view (header +
 * two stacked cards) so the layout doesn't jump on data arrival.
 */
export function AutomationDetailLoading() {
	return (
		<div className="space-y-6">
			<div className="space-y-3">
				<Skeleton className="h-4 w-32" />
				<div className="flex items-center gap-3">
					<Skeleton className="h-7 w-64" />
					<Skeleton className="h-5 w-16 rounded-md" />
				</div>
				<Skeleton className="h-4 w-96" />
			</div>

			<Card>
				<CardHeader>
					<Skeleton className="h-5 w-32" />
				</CardHeader>
				<CardContent className="space-y-4">
					<Skeleton className="h-4 w-3/4" />
					<Skeleton className="h-4 w-1/2" />
					<Skeleton className="h-24 w-full" />
				</CardContent>
			</Card>

			<Card>
				<CardHeader>
					<Skeleton className="h-5 w-24" />
				</CardHeader>
				<CardContent>
					<Skeleton className="h-20 w-full" />
				</CardContent>
			</Card>
		</div>
	);
}
