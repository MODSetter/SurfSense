import { getArtifactFormatMeta } from "./artifact-format-meta";

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
