import { useSetAtom } from "jotai";
import { useEffect, useRef, useState } from "react";
import { openArtifactPanelAtom } from "@/features/artifacts/state/artifact-panel.atom";
import { useMediaQuery } from "@/hooks/use-media-query";
import { ARTIFACT_QUERY_PARAM, artifactIdFromSearch } from "../lib/artifact-deep-link";
import { openChatArtifact } from "../lib/open-chat-artifact";
import type { ChatArtifact } from "../model/artifact";
import { closeArtifactsPanelAtom } from "../state/artifacts-panel.atom";

function removeArtifactTargetFromUrl(artifactId: number): void {
	const url = new URL(window.location.href);
	if (artifactIdFromSearch(url.search) !== artifactId) return;

	url.searchParams.delete(ARTIFACT_QUERY_PARAM);
	window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
}

/**
 * Resolve artifact navigation independently of thread rendering. Viewer
 * formats open their panel and inline media scrolls to its message card.
 */
export function useArtifactDeepLink(
	artifacts: readonly ChatArtifact[],
	isArtifactDataReady: boolean,
	routeKey: string
): void {
	const openArtifactPanel = useSetAtom(openArtifactPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const [targetArtifactId, setTargetArtifactId] = useState<number | null>(null);
	const currentRouteRef = useRef(routeKey);
	const currentTargetRef = useRef<number | null>(null);
	const processingTargetRef = useRef<number | null>(null);

	useEffect(() => {
		const artifactId = artifactIdFromSearch(window.location.search);
		currentRouteRef.current = routeKey;
		currentTargetRef.current = artifactId;
		processingTargetRef.current = null;
		setTargetArtifactId(artifactId);
	}, [routeKey]);

	useEffect(() => {
		if (targetArtifactId == null || processingTargetRef.current === targetArtifactId) return;

		const artifact = artifacts.find((item) => item.artifactId === targetArtifactId);
		if (!artifact) {
			if (isArtifactDataReady) {
				removeArtifactTargetFromUrl(targetArtifactId);
				currentTargetRef.current = null;
				setTargetArtifactId(null);
			}
			return;
		}

		const artifactId = artifact.artifactId;
		if (artifactId == null) return;
		processingTargetRef.current = targetArtifactId;
		void openChatArtifact({ ...artifact, artifactId }, "deep-link", {
			closeArtifactsPanel,
			isDesktop,
			openArtifactPanel,
		}).finally(() => {
			if (currentRouteRef.current !== routeKey || currentTargetRef.current !== targetArtifactId) {
				return;
			}
			removeArtifactTargetFromUrl(targetArtifactId);
			currentTargetRef.current = null;
			setTargetArtifactId(null);
		});
	}, [
		artifacts,
		closeArtifactsPanel,
		isArtifactDataReady,
		isDesktop,
		openArtifactPanel,
		routeKey,
		targetArtifactId,
	]);
}
