import { getArtifactFormatMeta } from "@/features/artifacts/lib/artifact-format-catalog";

export function ArtifactFormatIcon({
	format,
	className,
}: {
	format: string | null | undefined;
	className?: string;
}) {
	const Icon = getArtifactFormatMeta(format).icon;
	return <Icon className={className} aria-hidden="true" />;
}
