"use client";
import { History } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAutomationRuns } from "@/hooks/use-automation-runs";
import { RunRow } from "./run-row";
import { RunsLoading } from "./runs-loading";

interface AutomationRunsSectionProps {
	automationId: number;
}

const LIMIT = 20;

/**
 * Run history card. Shows the most recent ``LIMIT`` runs; pagination is
 * intentionally deferred — for the foreseeable v1 surface (one-trigger
 * automations firing daily), 20 covers ~3 weeks of history which is
 * enough to tell whether things are working. Real "load more" lands if
 * we see usage spike past that.
 */
export function AutomationRunsSection({ automationId }: AutomationRunsSectionProps) {
	const { data, isLoading, error } = useAutomationRuns(automationId, { limit: LIMIT });
	const runs = data?.items ?? [];

	return (
		<Card className="border-border/60 bg-accent">
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
				<div className="space-y-1">
					<CardTitle className="text-base font-semibold inline-flex items-center gap-2">
						<History className="h-4 w-4 text-muted-foreground" aria-hidden />
						Recent runs
					</CardTitle>
					<p className="text-xs text-muted-foreground">
						Most recent first. Click a row to inspect step results, output and artifacts.
					</p>
				</div>
				{!isLoading && !error && data && (
					<span className="text-xs text-muted-foreground">{data.total} total</span>
				)}
			</CardHeader>
			<CardContent>
				{isLoading ? (
					<RunsLoading />
				) : error ? (
					<p className="text-sm text-muted-foreground">
						Couldn't load runs{error.message ? `: ${error.message}` : "."}
					</p>
				) : runs.length === 0 ? (
					<div className="rounded-md border border-dashed border-border/60 bg-muted/20 px-4 py-8 text-center">
						<History className="mx-auto h-8 w-8 text-muted-foreground" aria-hidden />
						<p className="mt-2 text-sm font-medium text-foreground">No runs yet</p>
						<p className="mt-1 text-xs text-muted-foreground">
							This automation hasn't fired. Once a trigger fires (or you invoke it manually), runs
							will appear here.
						</p>
					</div>
				) : (
					<div className="space-y-2">
						{runs.map((run) => (
							<RunRow key={run.id} run={run} automationId={automationId} />
						))}
					</div>
				)}
			</CardContent>
		</Card>
	);
}
