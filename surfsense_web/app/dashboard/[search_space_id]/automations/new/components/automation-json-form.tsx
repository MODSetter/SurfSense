"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, Code, FileJson, Save } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { createAutomationMutationAtom } from "@/atoms/automations/automations-mutation.atoms";
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
 *   parse JSON → inject search_space_id → Zod validate → POST → navigate
 *
 * ``search_space_id`` is injected here rather than required in the pasted
 * payload — the user shouldn't have to know their numeric id, and it
 * keeps the template copy-paste-friendly across search spaces.
 */
export function AutomationJsonForm({ searchSpaceId }: AutomationJsonFormProps) {
	const router = useRouter();
	const { mutateAsync: createAutomation, isPending } = useAtomValue(createAutomationMutationAtom);
	const [text, setText] = useState(() => JSON.stringify(DEFAULT_AUTOMATION_TEMPLATE, null, 2));
	const [issues, setIssues] = useState<string[]>([]);

	function handleFormat() {
		try {
			const parsed = JSON.parse(text);
			setText(JSON.stringify(parsed, null, 2));
			setIssues([]);
		} catch (err) {
			setIssues([`Cannot format — not valid JSON: ${(err as Error).message}`]);
		}
	}

	async function handleSubmit() {
		setIssues([]);

		let parsed: unknown;
		try {
			parsed = JSON.parse(text);
		} catch (err) {
			setIssues([`Invalid JSON: ${(err as Error).message}`]);
			return;
		}

		if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
			setIssues(["Root must be a JSON object."]);
			return;
		}

		const payload = { ...(parsed as Record<string, unknown>), search_space_id: searchSpaceId };
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
			<CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
				<CardTitle className="text-base font-semibold inline-flex items-center gap-2">
					<FileJson className="h-4 w-4 text-muted-foreground" aria-hidden />
					Definition + triggers
				</CardTitle>
				<Button type="button" variant="outline" size="sm" onClick={handleFormat}>
					<Code className="mr-2 h-3.5 w-3.5" />
					Format
				</Button>
			</CardHeader>
			<CardContent className="space-y-4">
				<textarea
					value={text}
					onChange={(e) => setText(e.target.value)}
					spellCheck={false}
					rows={24}
					className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs font-mono text-foreground shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring resize-y min-h-[16rem]"
					aria-label="Automation JSON"
				/>

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
