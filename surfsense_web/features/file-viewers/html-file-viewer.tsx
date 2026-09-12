"use client";

import { useEffect, useState } from "react";
import { Spinner } from "@/components/ui/spinner";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { cannotPreviewMessage } from "./file-format";
import type { FileViewerProps } from "./model";
import { UnviewableFile } from "./unviewable-file";

export const HTML_MAX_VIEWER_BYTES = 15 * 1024 * 1024;
export const HTML_IFRAME_SANDBOX = "allow-scripts";

const CONTENT_SECURITY_POLICY = [
	"default-src 'none'",
	"script-src 'unsafe-inline'",
	"style-src 'unsafe-inline' https://fonts.googleapis.com",
	"font-src https://fonts.gstatic.com",
	"img-src data:",
	"connect-src 'none'",
	"form-action 'none'",
	"base-uri 'none'",
	"object-src 'none'",
	"frame-src 'none'",
	"navigate-to 'none'",
].join("; ");

export function buildHtmlArtifactDocument(fragment: string): string {
	return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="${CONTENT_SECURITY_POLICY}">
</head>
<body>
${fragment}
</body>
</html>`;
}

type LoadState =
	| { status: "loading" }
	| { status: "ready"; source: string }
	| { status: "error"; message: string };

class InvalidHtmlEncodingError extends Error {}

export default function HtmlFileViewer({ primary }: FileViewerProps) {
	const [state, setState] = useState<LoadState>({ status: "loading" });

	useEffect(() => {
		const controller = new AbortController();
		setState({ status: "loading" });

		if (primary.size_bytes > HTML_MAX_VIEWER_BYTES) {
			setState({
				status: "error",
				message: `${cannotPreviewMessage(primary.filename)} (file is too large to preview)`,
			});
			return () => controller.abort();
		}

		void (async () => {
			try {
				const response = await authenticatedFetch(buildBackendUrl(primary.content_url), {
					cache: "no-store",
					signal: controller.signal,
					skipAuthRedirect: true,
				});
				if (!response.ok) {
					throw new Error(`Could not load HTML artifact (${response.status})`);
				}
				const bytes = await response.arrayBuffer();
				if (controller.signal.aborted) return;
				if (bytes.byteLength > HTML_MAX_VIEWER_BYTES) {
					setState({
						status: "error",
						message: `${cannotPreviewMessage(primary.filename)} (file is too large to preview)`,
					});
					return;
				}
				let fragment: string;
				try {
					fragment = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
				} catch {
					throw new InvalidHtmlEncodingError();
				}
				setState({ status: "ready", source: buildHtmlArtifactDocument(fragment) });
			} catch (error) {
				if (controller.signal.aborted) return;
				const detail =
					error instanceof InvalidHtmlEncodingError
						? "file is not valid UTF-8"
						: "file could not be opened";
				setState({
					status: "error",
					message: `${cannotPreviewMessage(primary.filename)} (${detail})`,
				});
			}
		})();

		return () => controller.abort();
	}, [primary.content_url, primary.filename, primary.size_bytes]);

	if (state.status === "loading") {
		return (
			<div aria-busy="true" className="flex h-full items-center justify-center">
				<Spinner size="lg" />
			</div>
		);
	}

	if (state.status === "error") {
		return <UnviewableFile message={state.message} />;
	}

	return (
		<iframe
			className="h-full w-full border-0 bg-white"
			sandbox={HTML_IFRAME_SANDBOX}
			srcDoc={state.source}
			title={primary.filename}
		/>
	);
}
