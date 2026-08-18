"use client";

import { useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import type { DocumentsEmptyReason } from "@/lib/documents/documents-view-model";

export function DocumentsEmptyState({ reason }: { reason: DocumentsEmptyReason }) {
	const t = useTranslations("documents");

	if (reason.kind === "loading") {
		return (
			<output className="block space-y-1 px-4 py-2" aria-busy="true" aria-label={t("loading")}>
				{["loading-1", "loading-2", "loading-3", "loading-4", "loading-5"].map((key, index) => (
					<div key={key} className="flex h-8 items-center gap-2">
						<Skeleton className="size-4 rounded-sm" />
						<Skeleton className={index % 2 === 0 ? "h-4 w-44" : "h-4 w-32"} />
					</div>
				))}
			</output>
		);
	}

	const title =
		reason.kind === "workspace_empty" ? t("no_documents") : t("empty_no_matching_documents");
	const description =
		reason.kind === "workspace_empty"
			? t("empty_upload_files")
			: reason.kind === "no_search_results"
				? t("empty_try_different_search")
				: t("empty_adjust_filters");

	return (
		<output
			className="flex flex-1 select-none flex-col items-center justify-center gap-1 px-4 py-12 text-center text-muted-foreground"
			aria-live="polite"
		>
			<p className="text-sm font-medium">{title}</p>
			<p className="text-xs text-muted-foreground/70">{description}</p>
		</output>
	);
}
