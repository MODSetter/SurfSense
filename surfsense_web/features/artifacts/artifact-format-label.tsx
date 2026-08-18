import { Dot } from "lucide-react";
import { cn } from "@/lib/utils";
import { getArtifactFormatMeta } from "./artifact-format-meta";

export function ArtifactFormatLabel({
	format,
	className,
}: {
	format: string | null | undefined;
	className?: string;
}) {
	const { label, detailLabel } = getArtifactFormatMeta(format);

	return (
		<span className={cn("inline-flex items-center", className)}>
			<span>{label}</span>
			{detailLabel ? (
				<>
					<Dot className="size-4 shrink-0 text-muted-foreground/60" aria-hidden="true" />
					<span>{detailLabel}</span>
				</>
			) : null}
		</span>
	);
}
