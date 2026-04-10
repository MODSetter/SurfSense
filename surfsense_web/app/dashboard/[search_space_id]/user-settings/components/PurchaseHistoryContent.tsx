"use client";

import { useQuery } from "@tanstack/react-query";
import { ReceiptText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { PagePurchase, PagePurchaseStatus } from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<PagePurchaseStatus, { label: string; className: string }> = {
	completed: {
		label: "Completed",
		className: "bg-emerald-600 text-white border-transparent hover:bg-emerald-600",
	},
	pending: {
		label: "Pending",
		className: "bg-yellow-600 text-white border-transparent hover:bg-yellow-600",
	},
	failed: {
		label: "Failed",
		className: "bg-destructive text-white border-transparent hover:bg-destructive",
	},
};

function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

function formatAmount(purchase: PagePurchase): string {
	if (purchase.amount_total == null) return "—";
	const dollars = purchase.amount_total / 100;
	const currency = (purchase.currency ?? "usd").toUpperCase();
	return `$${dollars.toFixed(2)} ${currency}`;
}

export function PurchaseHistoryContent() {
	const { data, isLoading } = useQuery({
		queryKey: ["stripe-purchases"],
		queryFn: () => stripeApiService.getPurchases(),
	});

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	const purchases = data?.purchases ?? [];

	if (purchases.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
				<ReceiptText className="h-8 w-8 text-muted-foreground" />
				<p className="text-sm font-medium">No purchases yet</p>
				<p className="text-xs text-muted-foreground">
					Your page-pack purchases will appear here after checkout.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4">
			<div className="rounded-lg border">
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Date</TableHead>
							<TableHead className="text-right">Pages</TableHead>
							<TableHead className="text-right">Amount</TableHead>
							<TableHead className="text-center">Status</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{purchases.map((p) => {
							const style = STATUS_STYLES[p.status];
							return (
								<TableRow key={p.id}>
									<TableCell className="text-sm">{formatDate(p.created_at)}</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{p.pages_granted.toLocaleString()}
									</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{formatAmount(p)}
									</TableCell>
									<TableCell className="text-center">
										<Badge className={cn("text-[10px]", style.className)}>{style.label}</Badge>
									</TableCell>
								</TableRow>
							);
						})}
					</TableBody>
				</Table>
			</div>
			<p className="text-center text-xs text-muted-foreground">
				Showing your {purchases.length} most recent purchase{purchases.length !== 1 ? "s" : ""}.
			</p>
		</div>
	);
}
