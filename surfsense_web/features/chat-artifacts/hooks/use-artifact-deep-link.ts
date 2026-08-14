import { useSetAtom } from "jotai";
import { useEffect, useRef, useState } from "react";
import { openArtifactPanelAtom } from "@/atoms/chat/artifact-panel.atom";
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
 * Resolve a library link after both messages and persisted artifact metadata
 * hydrate. The caller keeps the existing chat skeleton visible until this
 * returns `false`, hiding assistant-ui's initialize-to-bottom positioning.
 */
export function useArtifactDeepLink(
	artifacts: readonly ChatArtifact[],
	isArtifactDataReady: boolean,
	routeKey: string
): boolean {
	const openArtifactPanel = useSetAtom(openArtifactPanelAtom);
	const closeArtifactsPanel = useSetAtom(closeArtifactsPanelAtom);
	const isDesktop = useMediaQuery("(min-width: 1024px)");
	const [targetArtifactId, setTargetArtifactId] = useState<number | null>(null);
	const currentRouteRef = useRef(routeKey);
	const currentTargetRef = useRef<number | null>(null);
	const processingTargetRef = useRef<number | null>(null);

	// The normal thread-loading skeleton is already present on navigation. This
	// keeps that state active when hydrated messages replace it.
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

		processingTargetRef.current = targetArtifactId;
		void openChatArtifact(artifact, "deep-link", {
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

	return targetArtifactId != null;
}
