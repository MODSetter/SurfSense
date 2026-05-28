"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { updateAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { JsonView } from "@/components/json-view";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
	type Automation,
	automationUpdateRequest,
} from "@/contracts/types/automation.types";

interface AutomationEditFormProps {
	automation: Automation;
	searchSpaceId: number;
}

/**
 * Edit-existing-automation form. Surfaces the four mutable fields
 * (name, description, status, definition) as one editable JSON tree;
 * triggers stay on the detail page where they have their own management
 * UI. Validates with the same Zod schema the API expects, then PATCHes
 * the changed shape back.
 */
export function AutomationEditForm({ automation, searchSpaceId }: AutomationEditFormProps) {
	const router = useRouter();
	const { mutateAsync: updateAutomation, isPending } = useAtomValue(updateAutomationMutationAtom);
	const detailHref = `/dashboard/${searchSpaceId}/automations/${automation.id}`;

	const [value, setValue] = useState(() => ({
		name: automation.name,
		description: automation.description ?? null,
		status: automation.status,
		definition: automation.definition,
	}));
	const [issues, setIssues] = useState<string[]>([]);

	async function handleSave() {
		setIssues([]);
		const result = automationUpdateRequest.safeParse(value);
		if (!result.success) {
			setIssues(
				result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
			);
			return;
		}
		try {
			await updateAutomation({ automationId: automation.id, patch: result.data });
			router.push(detailHref);
		} catch (err) {
			setIssues([(err as Error).message ?? "Update failed"]);
		}
	}

	return (
		<>
			<div className="space-y-3">
				<Button asChild variant="ghost" size="sm" className="-ml-2 h-auto px-2 py-1">
					<Link href={detailHref} className="text-xs text-muted-foreground">
						<ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
						Back to automation
					</Link>
				</Button>
				<div>
					<h1 className="text-xl md:text-2xl font-semibold text-foreground break-words">
						Edit automation
					</h1>
					<p className="text-sm text-muted-foreground mt-1">{automation.name}</p>
				</div>
			</div>

			<Card className="border-border/60 bg-accent">
				<CardHeader className="pb-4">
					<CardTitle className="text-base font-semibold">Definition</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					<div className="rounded-md border border-input bg-background px-3 py-2 max-h-[36rem] overflow-auto">
						<JsonView
							src={value}
							editable
							onChange={(next) => setValue(next as typeof value)}
							collapsed={false}
						/>
					</div>

					{issues.length > 0 && (
						<div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2">
							<div className="flex items-center gap-1.5 text-xs font-medium text-destructive mb-1.5">
								<AlertCircle className="h-3.5 w-3.5" aria-hidden />
								{issues.length === 1 ? "1 issue" : `${issues.length} issues`}
							</div>
							<ul className="space-y-0.5 text-xs text-destructive list-disc list-inside">
								{issues.map((issue) => (
									<li key={issue}>{issue}</li>
								))}
							</ul>
						</div>
					)}

					<div className="flex items-center justify-end gap-2">
						<Button asChild type="button" variant="ghost" size="sm">
							<Link href={detailHref}>Cancel</Link>
						</Button>
						<Button type="button" onClick={handleSave} disabled={isPending} size="sm">
							{isPending ? (
								<Spinner size="xs" className="mr-2" />
							) : (
								<Save className="mr-2 h-4 w-4" />
							)}
							Save changes
						</Button>
					</div>
				</CardContent>
			</Card>
		</>
	);
}
