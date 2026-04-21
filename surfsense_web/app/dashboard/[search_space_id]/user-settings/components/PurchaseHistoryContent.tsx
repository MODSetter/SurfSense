"use client";

import { useQueries } from "@tanstack/react-query";
import { Coins, FileText, ReceiptText } from "lucide-react";
import { useMemo } from "react";
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
import type {
	PagePurchase,
	PagePurchaseStatus,
	TokenPurchase,
} from "@/contracts/types/stripe.types";
import { stripeApiService } from "@/lib/apis/stripe-api.service";
import { cn } from "@/lib/utils";

type PurchaseKind = "pages" | "tokens";

type UnifiedPurchase = {
	id: string;
	kind: PurchaseKind;
	created_at: string;
	status: PagePurchaseStatus;
	granted: number;
	amount_total: number | null;
	currency: string | null;
};

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

const KIND_META: Record<
	PurchaseKind,
	{ label: string; icon: React.ComponentType<{ className?: string }>; iconClass: string }
> = {
	pages: {
		label: "Pages",
		icon: FileText,
		iconClass: "text-sky-500",
	},
	tokens: {
		label: "Premium Tokens",
		icon: Coins,
		iconClass: "text-amber-500",
	},
};

function formatDate(iso: string): string {
	return new Date(iso).toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

function formatAmount(amount: number | null, currency: string | null): string {
	if (amount == null) return "—";
	const dollars = amount / 100;
	const code = (currency ?? "usd").toUpperCase();
	return `$${dollars.toFixed(2)} ${code}`;
}

function normalizePagePurchase(p: PagePurchase): UnifiedPurchase {
	return {
		id: p.id,
		kind: "pages",
		created_at: p.created_at,
		status: p.status,
		granted: p.pages_granted,
		amount_total: p.amount_total,
		currency: p.currency,
	};
}

function normalizeTokenPurchase(p: TokenPurchase): UnifiedPurchase {
	return {
		id: p.id,
		kind: "tokens",
		created_at: p.created_at,
		status: p.status,
		granted: p.tokens_granted,
		amount_total: p.amount_total,
		currency: p.currency,
	};
}

export function PurchaseHistoryContent() {
	const results = useQueries({
		queries: [
			{
				queryKey: ["stripe-purchases"],
				queryFn: () => stripeApiService.getPurchases(),
			},
			{
				queryKey: ["stripe-token-purchases"],
				queryFn: () => stripeApiService.getTokenPurchases(),
			},
		],
	});

	const [pagesQuery, tokensQuery] = results;
	const isLoading = pagesQuery.isLoading || tokensQuery.isLoading;

	const purchases = useMemo<UnifiedPurchase[]>(() => {
		const pagePurchases = pagesQuery.data?.purchases ?? [];
		const tokenPurchases = tokensQuery.data?.purchases ?? [];
		return [
			...pagePurchases.map(normalizePagePurchase),
			...tokenPurchases.map(normalizeTokenPurchase),
		].sort(
			(a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
		);
	}, [pagesQuery.data, tokensQuery.data]);

	if (isLoading) {
		return (
			<div className="flex items-center justify-center py-12">
				<Spinner size="md" className="text-muted-foreground" />
			</div>
		);
	}

	if (purchases.length === 0) {
		return (
			<div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
				<ReceiptText className="h-8 w-8 text-muted-foreground" />
				<p className="text-sm font-medium">No purchases yet</p>
				<p className="text-xs text-muted-foreground">
					Your page and premium token purchases will appear here after checkout.
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
							<TableHead>Type</TableHead>
							<TableHead className="text-right">Granted</TableHead>
							<TableHead className="text-right">Amount</TableHead>
							<TableHead className="text-center">Status</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{purchases.map((p) => {
							const statusStyle = STATUS_STYLES[p.status];
							const kind = KIND_META[p.kind];
							const KindIcon = kind.icon;
							return (
								<TableRow key={`${p.kind}-${p.id}`}>
									<TableCell className="text-sm">{formatDate(p.created_at)}</TableCell>
									<TableCell className="text-sm">
										<div className="flex items-center gap-2">
											<KindIcon className={cn("h-4 w-4", kind.iconClass)} />
											<span>{kind.label}</span>
										</div>
									</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{p.granted.toLocaleString()}
									</TableCell>
									<TableCell className="text-right tabular-nums text-sm">
										{formatAmount(p.amount_total, p.currency)}
									</TableCell>
									<TableCell className="text-center">
										<Badge className={cn("text-[10px]", statusStyle.className)}>
											{statusStyle.label}
										</Badge>
									</TableCell>
								</TableRow>
							);
						})}
					</TableBody>
				</Table>
			</div>
			<p className="text-center text-xs text-muted-foreground">
				Showing your {purchases.length} most recent purchase
				{purchases.length !== 1 ? "s" : ""}.
			</p>
		</div>
	);
}
