"use client";

import { useParams } from "next/navigation";
import { ArtifactsLibrary } from "@/features/artifacts-library";

export default function ArtifactsPage() {
	const params = useParams();
	const workspaceId = Number(params.workspace_id);

	return <ArtifactsLibrary workspaceId={workspaceId} />;
}
