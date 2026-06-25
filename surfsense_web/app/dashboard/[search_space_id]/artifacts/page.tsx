"use client";

import { useParams } from "next/navigation";
import { ArtifactsLibrary } from "@/features/artifacts-library";

export default function ArtifactsPage() {
	const params = useParams();
	const searchSpaceId = Number(params.search_space_id);

	return <ArtifactsLibrary searchSpaceId={searchSpaceId} />;
}
