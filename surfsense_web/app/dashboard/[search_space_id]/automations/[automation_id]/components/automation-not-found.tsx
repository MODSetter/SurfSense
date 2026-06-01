"use client";
import { ArrowLeft, FileWarning } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

interface AutomationNotFoundProps {
	searchSpaceId: number;
	error?: Error | null;
}

/**
 * Rendered when the detail fetch fails (404 / 403 / network) or the id
 * is not a number. We don't distinguish "missing" from "forbidden" in the
 * UI on purpose — leaking that an id exists you can't read is worse than
 * a vague message.
 */
export function AutomationNotFound({ searchSpaceId, error }: AutomationNotFoundProps) {
	return (
		<div className="rounded-lg border border-border/60 bg-muted/20 px-6 py-12 text-center">
			<FileWarning className="mx-auto h-10 w-10 text-muted-foreground" aria-hidden />
			<h2 className="mt-3 text-base font-semibold text-foreground">Automation not found</h2>
			<p className="mt-1 text-sm text-muted-foreground max-w-md mx-auto">
				This automation doesn't exist or you don't have access to it.
				{error?.message ? ` (${error.message})` : null}
			</p>
			<Button asChild variant="outline" size="sm" className="mt-6">
				<Link href={`/dashboard/${searchSpaceId}/automations`}>
					<ArrowLeft className="mr-2 h-4 w-4" />
					Back to automations
				</Link>
			</Button>
		</div>
	);
}
