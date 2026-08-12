"use client";

import {
	AlertCircleIcon,
	AlertTriangleIcon,
	CheckCircle2Icon,
	ChevronRightIcon,
	FileCheck2Icon,
	Loader2Icon,
} from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { TimelineToolProps } from "@/features/chat-messages/timeline/tool-registry/types";
import { cn } from "@/lib/utils";

const ResultSchema = z.object({
	status: z.enum(["verified", "failed"]),
	findings: z.array(z.string()).default([]),
	notes: z.array(z.string()).default([]),
	page_count: z.number().nullish(),
	verification_unavailable: z.string().nullish(),
});

function parseResult(result: unknown) {
	const direct = ResultSchema.safeParse(result);
	if (direct.success) return direct.data;
	if (result && typeof result === "object" && "result" in result) {
		const nested = ResultSchema.safeParse((result as { result: unknown }).result);
		if (nested.success) return nested.data;
	}
	return null;
}

export function VerifyArtifactToolUI({ result, status }: TimelineToolProps) {
	const [open, setOpen] = useState(false);

	if (status === "pending" || status === "running") {
		return (
			<div
				className="my-4 flex max-w-lg items-center gap-3 rounded-xl border bg-card px-4 py-3"
				aria-busy="true"
			>
				<Loader2Icon className="size-4 shrink-0 animate-spin text-muted-foreground" />
				<span className="text-sm text-muted-foreground">Verifying document</span>
			</div>
		);
	}

	const parsed = parseResult(result);
	const verified = parsed?.status === "verified";
	const unavailable = verified && Boolean(parsed.verification_unavailable);
	const clean = verified && !unavailable;
	const label = clean
		? "Document verified"
		: unavailable
			? "Visual review unavailable"
			: "Document needs changes";
	const details = [...(parsed?.findings ?? []), ...(parsed?.notes ?? [])];
	if (parsed?.verification_unavailable) details.push(parsed.verification_unavailable);
	const hasDetails = details.length > 0;

	return (
		<div className="my-4 max-w-lg">
			<Collapsible open={open} onOpenChange={setOpen}>
				<CollapsibleTrigger
					disabled={!hasDetails}
					className={cn(
						"flex w-full items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-left transition-colors hover:bg-accent",
						open && "rounded-b-none border-b-0",
						!verified && "border-destructive/20",
						unavailable && "border-amber-500/20"
					)}
				>
					<ChevronRightIcon
						className={cn(
							"size-3.5 shrink-0 text-muted-foreground transition-transform",
							open && "rotate-90",
							!hasDetails && "invisible"
						)}
					/>
					<FileCheck2Icon className="size-3.5 shrink-0 text-muted-foreground" />
					<span className="min-w-0 flex-1 truncate text-sm">{label}</span>
					{parsed?.page_count ? <Badge variant="outline">{parsed.page_count} pages</Badge> : null}
					{clean ? (
						<CheckCircle2Icon className="size-4 text-emerald-600" />
					) : unavailable ? (
						<AlertTriangleIcon className="size-4 text-amber-600" />
					) : (
						<AlertCircleIcon className="size-4 text-destructive" />
					)}
				</CollapsibleTrigger>
				<CollapsibleContent>
					<ul className="space-y-2 rounded-b-xl border border-t-0 bg-muted/20 px-4 py-3 text-sm">
						{details.map((detail) => (
							<li key={detail}>{detail}</li>
						))}
					</ul>
				</CollapsibleContent>
			</Collapsible>
		</div>
	);
}
