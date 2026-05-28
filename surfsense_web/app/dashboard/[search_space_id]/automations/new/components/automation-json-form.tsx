"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, FileJson, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
import { JsonView } from "@/components/json-view";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { automationCreateRequest } from "@/contracts/types/automation.types";
import { DEFAULT_AUTOMATION_TEMPLATE } from "@/lib/automations/default-template";

interface AutomationJsonFormProps {
	searchSpaceId: number;
}

/**
 * Raw-JSON create form. Lets power users skip the chat drafter when they
 * already know the shape they want. Flow:
 *   edit tree → inject search_space_id → Zod validate → POST → navigate
 *
 * ``search_space_id`` is injected here rather than required in the edited
 * tree — the user shouldn't have to know their numeric id, and it keeps
 * the template copy-paste-friendly across search spaces.
 */
export function AutomationJsonForm({ searchSpaceId }: AutomationJsonFormProps) {
	const router = useRouter();
	const { mutateAsync: createAutomation, isPending } = useAtomValue(createAutomationMutationAtom);
	const [value, setValue] = useState<Record<string, unknown>>(
		() => DEFAULT_AUTOMATION_TEMPLATE as Record<string, unknown>
	);
	const [issues, setIssues] = useState<string[]>([]);

	async function handleSubmit() {
		setIssues([]);

		const payload = { ...value, search_space_id: searchSpaceId };
		const result = automationCreateRequest.safeParse(payload);
		if (!result.success) {
			setIssues(
				result.error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`)
			);
			return;
		}

		try {
			const created = await createAutomation(result.data);
			router.push(`/dashboard/${searchSpaceId}/automations/${created.id}`);
		} catch (err) {
			setIssues([(err as Error).message ?? "Submit failed"]);
		}
	}

	const hasIssues = issues.length > 0;

	return (
		<Card className="border-border/60 bg-accent">
			<CardHeader className="pb-4">
				<CardTitle className="text-base font-semibold inline-flex items-center gap-2">
					<FileJson className="h-4 w-4 text-muted-foreground" aria-hidden />
					Definition + triggers
				</CardTitle>
			</CardHeader>
			<CardContent className="space-y-4">
				<div className="rounded-md border border-input bg-background px-3 py-2 max-h-[32rem] overflow-auto">
					<JsonView
						src={value}
						editable
						onChange={(next) => setValue(next as Record<string, unknown>)}
						collapsed={false}
					/>
				</div>

				{hasIssues && (
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
					<Button type="button" onClick={handleSubmit} disabled={isPending} size="sm">
						{isPending ? <Spinner size="xs" className="mr-2" /> : <Save className="mr-2 h-4 w-4" />}
						Create automation
					</Button>
				</div>
			</CardContent>
		</Card>
	);
}
