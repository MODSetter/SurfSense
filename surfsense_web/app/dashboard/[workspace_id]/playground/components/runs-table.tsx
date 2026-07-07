"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, History, Info } from "lucide-react";
import { Fragment, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { scrapersApiService } from "@/lib/apis/scrapers-api.service";
import { formatRelativeDate } from "@/lib/format-date";
import { PLAYGROUND_PLATFORMS } from "@/lib/playground/catalog";
import { formatCost, formatDuration } from "@/lib/playground/format";
import { cacheKeys } from "@/lib/query-client/cache-keys";
import { cn } from "@/lib/utils";
import { RunDetail } from "./run-detail";
import { RunStatusBadge } from "./run-status-badge";

const PAGE_SIZE = 25;
const ALL = "__all__";

const CAPABILITY_OPTIONS = PLAYGROUND_PLATFORMS.flatMap((platform) =>
	platform.verbs.map((verb) => verb.name)
);

export function RunsTable({ workspaceId }: { workspaceId: number }) {
	const [capability, setCapability] = useState<string>(ALL);
	const [status, setStatus] = useState<string>(ALL);
	const [expanded, setExpanded] = useState<string | null>(null);

	const filters = {
		capability: capability === ALL ? undefined : capability,
		status: status === ALL ? undefined : status,
	};

	const query = useInfiniteQuery({
		queryKey: [...cacheKeys.scrapers.runs(workspaceId), filters],
		queryFn: ({ pageParam }) =>
			scrapersApiService.listRuns(workspaceId, {
				limit: PAGE_SIZE,
				offset: pageParam,
				...filters,
			}),
		initialPageParam: 0,
		getNextPageParam: (lastPage, allPages) =>
			lastPage.length === PAGE_SIZE ? allPages.length * PAGE_SIZE : undefined,
		// Poll while any visible run is still in flight so it flips to a terminal
		// state without a manual refresh; idle otherwise.
		refetchInterval: (q) =>
			q.state.data?.pages.flat().some((r) => r.status === "running") ? 5000 : false,
	});

	const runs = query.data?.pages.flat() ?? [];

	return (
		<div className="space-y-4">
			<Alert>
				<Info />
				<AlertDescription>
					View all API runs for this workspace, including runs from the playground, API keys, and agents.
				</AlertDescription>
			</Alert>

			<div className="flex flex-wrap items-center gap-2">
				<Select value={capability} onValueChange={setCapability}>
					<SelectTrigger className="w-48">
						<SelectValue placeholder="All APIs" />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value={ALL}>All APIs</SelectItem>
						{CAPABILITY_OPTIONS.map((name) => (
							<SelectItem key={name} value={name}>
								{name}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
				<Select value={status} onValueChange={setStatus}>
					<SelectTrigger className="w-40">
						<SelectValue placeholder="All statuses" />
					</SelectTrigger>
					<SelectContent>
						<SelectItem value={ALL}>All statuses</SelectItem>
						<SelectItem value="running">Running</SelectItem>
						<SelectItem value="success">Success</SelectItem>
						<SelectItem value="error">Error</SelectItem>
						<SelectItem value="cancelled">Cancelled</SelectItem>
					</SelectContent>
				</Select>
			</div>

			{query.isLoading ? (
				<div className="flex h-48 items-center justify-center">
					<Spinner size="lg" />
				</div>
			) : query.isError ? (
				<p className="text-sm text-destructive">
					Couldn't load runs{query.error.message ? `: ${query.error.message}` : "."}
				</p>
			) : runs.length === 0 ? (
				<div className="rounded-md border border-dashed border-border/60 bg-muted/20 px-4 py-12 text-center">
					<History className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden />
					<p className="mt-2 text-sm font-medium">No runs yet</p>
					<p className="mt-1 text-xs text-muted-foreground">
						Run an API from the playground and it will show up here.
					</p>
				</div>
			) : (
				<div className="overflow-hidden rounded-md border border-border/60">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead className="w-8" />
								<TableHead>API</TableHead>
								<TableHead>Origin</TableHead>
								<TableHead>Status</TableHead>
								<TableHead className="text-right">Items</TableHead>
								<TableHead className="text-right">Duration</TableHead>
								<TableHead className="text-right">Cost</TableHead>
								<TableHead className="text-right">When</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{runs.map((run) => {
								const isOpen = expanded === run.id;
								return (
									<Fragment key={run.id}>
										<TableRow
											className="cursor-pointer"
											onClick={() => setExpanded(isOpen ? null : run.id)}
										>
											<TableCell>
												{isOpen ? (
													<ChevronDown className="h-4 w-4 text-muted-foreground" />
												) : (
													<ChevronRight className="h-4 w-4 text-muted-foreground" />
												)}
											</TableCell>
											<TableCell className="font-mono text-xs">{run.capability}</TableCell>
											<TableCell className="text-xs text-muted-foreground">{run.origin}</TableCell>
											<TableCell>
												<RunStatusBadge status={run.status} />
											</TableCell>
											<TableCell className="text-right tabular-nums">{run.item_count}</TableCell>
											<TableCell className="text-right tabular-nums text-muted-foreground">
												{formatDuration(run.duration_ms)}
											</TableCell>
											<TableCell className="text-right tabular-nums text-muted-foreground">
												{formatCost(run.cost_micros)}
											</TableCell>
											<TableCell className="text-right text-xs text-muted-foreground">
												{formatRelativeDate(run.created_at)}
											</TableCell>
										</TableRow>
										{isOpen && (
											<TableRow className="hover:bg-transparent">
												<TableCell colSpan={8} className="p-0">
													<RunDetail workspaceId={workspaceId} runId={run.id} />
												</TableCell>
											</TableRow>
										)}
									</Fragment>
								);
							})}
						</TableBody>
					</Table>
				</div>
			)}

			{query.hasNextPage && (
				<div className="flex justify-center">
					<Button
						type="button"
						variant="outline"
						onClick={() => query.fetchNextPage()}
						disabled={query.isFetchingNextPage}
						className={cn(query.isFetchingNextPage && "opacity-70")}
					>
						{query.isFetchingNextPage ? "Loading…" : "Load more"}
					</Button>
				</div>
			)}
		</div>
	);
}
