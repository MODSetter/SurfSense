"use client";

import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function EditConnectorLoadingSkeleton() {
	return (
		<div className="container mx-auto py-8 max-w-3xl">
			<Skeleton className="h-8 w-48 mb-6" />
			<Card className="border-2 border-border">
				<CardHeader>
					<Skeleton className="h-7 w-3/4 mb-2" />
					<Skeleton className="h-4 w-full" />
				</CardHeader>
				<CardContent className="space-y-4">
					<Skeleton className="h-10 w-full" />
					<Skeleton className="h-20 w-full" />
				</CardContent>
			</Card>
		</div>
	);
}
