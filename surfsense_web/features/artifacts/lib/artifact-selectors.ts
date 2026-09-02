import type { ArtifactFile, ArtifactManifest } from "@/features/artifacts/model/artifact";

export function selectPrimaryArtifactFile(
	manifest: ArtifactManifest | null | undefined
): ArtifactFile | undefined {
	return manifest?.files.find((file) => file.role === "primary");
}

export function artifactDownloadFilename(
	manifest: ArtifactManifest | null | undefined,
	artifactId: number
): string {
	return (
		selectPrimaryArtifactFile(manifest)?.filename ??
		(manifest ? `${manifest.title}.md` : `artifact-${artifactId}`)
	);
}
