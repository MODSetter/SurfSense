"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardFooter,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { useSession } from "@/hooks/use-session";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { redirectToLogin } from "@/lib/auth-utils";
import { buildBackendUrl } from "@/lib/env-config";

const FALLBACK_FILENAME = "surfsense-export.zip";
const DISPOSITION_FILENAME = /filename\*?=(?:UTF-8'')?"?([^";]+)/i;

export function filenameFromDisposition(header: string | null): string {
	if (!header) return FALLBACK_FILENAME;
	const match = header.match(DISPOSITION_FILENAME);
	const name = match?.[1]?.trim();
	return name || FALLBACK_FILENAME;
}

function triggerDownload(blob: Blob, filename: string) {
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = filename;
	document.body.appendChild(a);
	a.click();
	a.remove();
	URL.revokeObjectURL(url);
}

export function SunsetExport() {
	const session = useSession();
	const [isExporting, setIsExporting] = useState(false);

	async function handleExport() {
		if (isExporting) return;
		if (session.status !== "authenticated") {
			redirectToLogin();
			return;
		}

		setIsExporting(true);
		try {
			const response = await authenticatedFetch(buildBackendUrl("/api/v1/export"), {
				method: "GET",
				skipAuthRedirect: true,
			});
			if (response.status === 401) {
				redirectToLogin();
				return;
			}
			if (!response.ok) {
				const errorData = await response.json().catch(() => ({ detail: "Export failed" }));
				throw new Error(
					typeof errorData.detail === "string" ? errorData.detail : "Export failed"
				);
			}

			const blob = await response.blob();
			triggerDownload(blob, filenameFromDisposition(response.headers.get("Content-Disposition")));

			const skipped = response.headers.get("X-Skipped-Documents");
			toast.success(
				skipped
					? `Account exported. ${skipped} document${skipped === "1" ? "" : "s"} skipped.`
					: "Account exported"
			);
		} catch (err) {
			toast.error(err instanceof Error ? err.message : "Export failed");
		} finally {
			setIsExporting(false);
		}
	}

	const sessionLoading = session.status === "loading";
	const busy = sessionLoading || isExporting;
	const signedIn = session.status === "authenticated";

	return (
		<Card className="bg-card/80">
			<CardHeader>
				<CardTitle className="text-balance">Export your account</CardTitle>
				<CardDescription className="text-pretty">
					Downloads every workspace you can access: ready documents as markdown, folder structure,
					and chat threads.
				</CardDescription>
			</CardHeader>
			<CardContent>
				<p className="text-pretty text-sm text-muted-foreground">
					Original uploads, generated artifacts, tool calls, agent steps, and live citation links
					are not included.
				</p>
			</CardContent>
			<CardFooter>
				<Button
					type="button"
					size="lg"
					disabled={busy}
					onClick={() => void handleExport()}
					className="relative min-h-11 w-fit shrink-0 active:scale-[0.96] transition-transform"
				>
					<span className={busy ? "opacity-0" : ""}>
						{signedIn ? "Export account" : "Sign in to export"}
					</span>
					{busy ? <Spinner size="sm" className="absolute" /> : null}
				</Button>
			</CardFooter>
		</Card>
	);
}
