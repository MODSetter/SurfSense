"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { artifactListQueryOptions } from "./artifact-query";
import type { ArtifactListItem } from "./model";

export function useArtifactsByDocument(workspaceId: number): ReadonlyMap<number, ArtifactListItem> {
	const { data = [] } = useQuery({
		...artifactListQueryOptions(workspaceId),
		enabled: Number.isFinite(workspaceId) && workspaceId > 0,
	});

	return useMemo(() => new Map(data.map((artifact) => [artifact.document_id, artifact])), [data]);
}
