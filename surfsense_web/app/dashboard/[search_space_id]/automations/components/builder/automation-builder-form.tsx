"use client";
import { useAtomValue } from "jotai";
import { AlertCircle, Code2, LayoutList } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import type { z } from "zod";
import {
	addTriggerMutationAtom,
	createAutomationMutationAtom,
	removeTriggerMutationAtom,
	updateAutomationMutationAtom,
	updateTriggerMutationAtom,
} from "@/atoms/automations/automations-mutation.atoms";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
	type Automation,
	automationCreateRequest,
	automationUpdateRequest,
} from "@/contracts/types/automation.types";
import { useAutomationEligibleModels } from "@/hooks/use-automation-eligible-models";
import {
	type BuilderForm,
	type BuilderModels,
	buildCreatePayload,
	builderFormSchema,
	buildScheduleTrigger,
	buildUpdatePayload,
	createEmptyForm,
	formFromAutomation,
	type HydratableTrigger,
	hasResolvedModels,
	hydrateForm,
} from "@/lib/automations/builder-schema";
import { AdvancedSection } from "./advanced-section";
import { AutomationModelFields } from "./automation-model-fields";
import { BasicsSection } from "./basics-section";
import { BuilderSummary } from "./builder-summary";
import { JsonModePanel } from "./json-mode-panel";
import { ScheduleSection } from "./schedule-section";
import { TaskList } from "./task-list";
import { UnattendedToggle } from "./unattended-toggle";

interface AutomationBuilderFormProps {
	mode: "create" | "edit";
	searchSpaceId: number;
	/** Required in edit mode; seeds the form and trigger reconciliation. */
	automation?: Automation;
	/**
	 * Optional extra create-mode block reason (composed with the form's own
	 * model-eligibility gate). Shown as the submit button's tooltip. Model
	 * eligibility itself is now owned by the in-form pickers.
	 */
	submitDisabledReason?: string;
	renderModeSwitcher?: (modeSwitcher: ReactNode) => ReactNode;
}

type Mode = "form" | "json";

function mapFormErrors(error: z.ZodError): Record<string, string> {
	const out: Record<string, string> = {};
	for (const issue of error.issues) {
		const path = issue.path;
		let key: string;
		if (path[0] === "tasks" && typeof path[1] === "number") key = `tasks.${path[1]}.query`;
		else if (path[0] === "schedule") key = "schedule";
		else key = String(path[0] ?? "_root");
		if (!out[key]) out[key] = issue.message;
	}
	return out;
}

export function AutomationBuilderForm({
	mode,
	searchSpaceId,
	automation,
	submitDisabledReason,
	renderModeSwitcher,
}: AutomationBuilderFormProps) {
	const router = useRouter();
	const { mutateAsync: createAutomation } = useAtomValue(createAutomationMutationAtom);
	const { mutateAsync: updateAutomation } = useAtomValue(updateAutomationMutationAtom);
	const { mutateAsync: addTrigger } = useAtomValue(addTriggerMutationAtom);
	const { mutateAsync: updateTrigger } = useAtomValue(updateTriggerMutationAtom);
	const { mutateAsync: removeTrigger } = useAtomValue(removeTriggerMutationAtom);

	// Initial state: create starts empty in form mode; edit hydrates, falling
	// back to JSON mode when the definition can't be represented in the form.
	const initial = useMemo(() => {
		if (mode === "edit" && automation) {
			const result = formFromAutomation(automation);
			if (result.formable) {
				return { mode: "form" as Mode, form: result.form, notice: undefined };
			}
			return {
				mode: "json" as Mode,
				form: createEmptyForm(),
				notice: `This automation ${result.reason}, which the form can't show. Edit it as JSON below`,
			};
		}
		return { mode: "form" as Mode, form: createEmptyForm(), notice: undefined };
	}, [mode, automation]);

	const [activeMode, setActiveMode] = useState<Mode>(initial.mode);
	const [form, setForm] = useState<BuilderForm>(initial.form);
	const [errors, setErrors] = useState<Record<string, string>>({});
	const [rootError, setRootError] = useState<string | null>(null);

	const [jsonValue, setJsonValue] = useState<Record<string, unknown>>(() =>
		initial.mode === "json" ? jsonFromAutomation(automation) : {}
	);
	const [jsonIssues, setJsonIssues] = useState<string[]>([]);
	const [jsonNotice, setJsonNotice] = useState<string | undefined>(initial.notice);

	const [submitting, setSubmitting] = useState(false);

	// Eligible models + the search-space-seeded defaults. Models are chosen per
	// automation on create; in edit mode the backend preserves the captured
	// snapshot, so the picker is create-only.
	const eligibleModels = useAutomationEligibleModels();

	// Resolve each slot during render: an explicit (non-zero) pick wins,
	// otherwise fall back to the eligible default. No effect copies async hook
	// data into state, so there's no flicker/loop and the user's pick is sticky.
	const resolvedModels = useMemo<BuilderModels>(
		() => ({
			agentLlmId: form.models.agentLlmId || eligibleModels.llm.defaultId || 0,
			imageConfigId: form.models.imageConfigId || eligibleModels.image.defaultId || 0,
			visionConfigId: form.models.visionConfigId || eligibleModels.vision.defaultId || 0,
		}),
		[
			form.models,
			eligibleModels.llm.defaultId,
			eligibleModels.image.defaultId,
			eligibleModels.vision.defaultId,
		]
	);

	// The form with resolved models folded in — what every payload builder reads.
	const formForPayload = useMemo<BuilderForm>(
		() => ({ ...form, models: resolvedModels }),
		[form, resolvedModels]
	);

	function patchForm(patch: Partial<BuilderForm>) {
		setForm((prev) => ({ ...prev, ...patch }));
	}

	function jsonFromCurrentForm(): Record<string, unknown> {
		if (mode === "edit" && automation) {
			return { ...buildUpdatePayload(formForPayload), status: automation.status };
		}
		const { search_space_id: _ignored, ...rest } = buildCreatePayload(
			formForPayload,
			searchSpaceId
		);
		return rest;
	}

	function switchToJson() {
		setJsonValue(jsonFromCurrentForm());
		setJsonIssues([]);
		setJsonNotice(undefined);
		setActiveMode("json");
	}

	function switchToForm() {
		const result = tryJsonToForm();
		if (result.ok) {
			setForm(result.form);
			setErrors({});
			setRootError(null);
			setActiveMode("form");
			return;
		}
		setJsonIssues(result.issues);
		setJsonNotice(result.notice);
	}

	function tryJsonToForm():
		| { ok: true; form: BuilderForm }
		| { ok: false; issues: string[]; notice?: string } {
		// Read the raw tree defensively rather than strict-validating: an
		// incomplete JSON edit should still round-trip into the form, where the
		// form's own validation enforces completeness on submit.
		const definition = jsonValue.definition;
		if (!definition || typeof definition !== "object") {
			return { ok: false, issues: [], notice: "Add a definition before switching to the form" };
		}

		const name =
			typeof jsonValue.name === "string"
				? jsonValue.name
				: mode === "edit" && automation
					? automation.name
					: "";
		const description = typeof jsonValue.description === "string" ? jsonValue.description : null;
		const triggers =
			mode === "edit" && automation
				? (automation.triggers ?? [])
				: extractTriggers(jsonValue.triggers);

		const h = hydrateForm(name, description, definition, triggers);
		return h.formable
			? { ok: true, form: h.form }
			: { ok: false, issues: [], notice: `Can't show in the form: it ${h.reason}` };
	}

	function validateForm(): Record<string, string> | null {
		const result = builderFormSchema.safeParse(form);
		const next = result.success ? {} : mapFormErrors(result.error);

		// The schedule model fields aren't deeply validated by the schema.
		if (form.schedule?.mode === "preset") {
			const m = form.schedule.model;
			if (m.frequency === "weekly" && m.daysOfWeek.length === 0) {
				next.schedule = "Pick at least one day for the weekly schedule";
			}
		} else if (form.schedule?.mode === "cron" && !form.schedule.cron.trim()) {
			next.schedule = "Enter a schedule expression";
		}

		return Object.keys(next).length > 0 ? next : null;
	}

	async function reconcileTriggers(automationId: number) {
		const desired = buildScheduleTrigger(form);
		const existing = (automation?.triggers ?? [])[0];
		if (!existing && desired) {
			await addTrigger({ automationId, payload: desired });
		} else if (existing && !desired) {
			await removeTrigger({ automationId, triggerId: existing.id });
		} else if (existing && desired) {
			await updateTrigger({
				automationId,
				triggerId: existing.id,
				patch: { params: desired.params, enabled: desired.enabled },
			});
		}
	}

	async function submitForm() {
		setRootError(null);
		const formErrors = validateForm();
		if (formErrors) {
			setErrors(formErrors);
			return;
		}
		setErrors({});

		setSubmitting(true);
		try {
			if (mode === "edit" && automation) {
				const payload = buildUpdatePayload(formForPayload);
				const parsed = automationUpdateRequest.safeParse(payload);
				if (!parsed.success) {
					setRootError(zodIssueList(parsed.error).join("; "));
					return;
				}
				await updateAutomation({ automationId: automation.id, patch: parsed.data });
				await reconcileTriggers(automation.id);
				router.push(`/dashboard/${searchSpaceId}/automations/${automation.id}`);
			} else {
				const payload = buildCreatePayload(formForPayload, searchSpaceId);
				const parsed = automationCreateRequest.safeParse(payload);
				if (!parsed.success) {
					setRootError(zodIssueList(parsed.error).join("; "));
					return;
				}
				const created = await createAutomation(parsed.data);
				router.push(`/dashboard/${searchSpaceId}/automations/${created.id}`);
			}
		} catch (err) {
			setRootError((err as Error).message ?? "Submit failed");
		} finally {
			setSubmitting(false);
		}
	}

	async function submitJson() {
		setJsonIssues([]);
		setSubmitting(true);
		try {
			if (mode === "edit" && automation) {
				const parsed = automationUpdateRequest.safeParse(jsonValue);
				if (!parsed.success) {
					setJsonIssues(zodIssueList(parsed.error));
					return;
				}
				await updateAutomation({ automationId: automation.id, patch: parsed.data });
				router.push(`/dashboard/${searchSpaceId}/automations/${automation.id}`);
			} else {
				const parsed = automationCreateRequest.safeParse({
					...jsonValue,
					search_space_id: searchSpaceId,
				});
				if (!parsed.success) {
					setJsonIssues(zodIssueList(parsed.error));
					return;
				}
				const created = await createAutomation(parsed.data);
				router.push(`/dashboard/${searchSpaceId}/automations/${created.id}`);
			}
		} catch (err) {
			setJsonIssues([(err as Error).message ?? "Submit failed"]);
		} finally {
			setSubmitting(false);
		}
	}

	const submitLabel = mode === "edit" ? "Save changes" : "Create automation";
	// Block creation until every model slot resolves to an eligible id. The
	// per-field Alert already explains *why* a slot is empty; this just guards
	// submit. `submitDisabledReason` (from the caller) still composes in.
	const modelsUnresolved =
		mode === "create" && !eligibleModels.isLoading && !hasResolvedModels(resolvedModels);
	const effectiveDisabledReason =
		submitDisabledReason ??
		(modelsUnresolved
			? "Set up a premium or your own (BYOK) agent, image, and vision model in role settings before creating an automation."
			: undefined);
	// Only gate creation; editing an existing automation isn't blocked here.
	const submitBlocked = mode === "create" && !!effectiveDisabledReason;
	const modeSwitcher = (
		<Tabs
			value={activeMode}
			onValueChange={(value) => {
				if (value === activeMode) return;
				if (value === "form") switchToForm();
				else if (value === "json") switchToJson();
			}}
		>
			<TabsList className="h-6 gap-0 rounded-md bg-muted/60 p-0.5 select-none">
				<TabsTrigger
					value="form"
					className="h-5 gap-1 px-1.5 text-[11px] select-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=active]:bg-muted-foreground/25 data-[state=active]:text-foreground data-[state=active]:shadow-none"
				>
					<LayoutList className="size-3 shrink-0" />
					<span className="leading-none">Form</span>
				</TabsTrigger>
				<TabsTrigger
					value="json"
					className="h-5 gap-1 px-1.5 text-[11px] select-none focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=active]:bg-muted-foreground/25 data-[state=active]:text-foreground data-[state=active]:shadow-none"
				>
					<Code2 className="size-3 shrink-0" />
					<span className="leading-none">Edit as JSON</span>
				</TabsTrigger>
			</TabsList>
		</Tabs>
	);

	return (
		<div className="space-y-4">
			{renderModeSwitcher ? (
				renderModeSwitcher(modeSwitcher)
			) : (
				<div className="flex items-center justify-end">{modeSwitcher}</div>
			)}

			{activeMode === "json" ? (
				<Card className="rounded-md border-accent bg-accent/20">
					<CardContent className="pt-6">
						<JsonModePanel
							value={jsonValue}
							issues={jsonIssues}
							notice={jsonNotice}
							onChange={setJsonValue}
						/>
					</CardContent>
				</Card>
			) : (
				<div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
					<div className="lg:col-span-2">
						<Card className="rounded-md border-accent bg-accent/20">
							<section>
								<CardHeader className="pb-3">
									<CardTitle className="text-sm font-semibold">Basics</CardTitle>
								</CardHeader>
								<CardContent>
									<BasicsSection
										name={form.name}
										description={form.description}
										errors={errors}
										onChange={patchForm}
									/>
								</CardContent>
							</section>
							<Separator className="mx-auto data-[orientation=horizontal]:w-[calc(100%-6rem)]" />
							<section>
								<CardHeader className="pb-3">
									<CardTitle className="text-sm font-semibold">Tasks</CardTitle>
								</CardHeader>
								<CardContent className="space-y-4">
									<TaskList
										tasks={form.tasks}
										errors={errors}
										searchSpaceId={searchSpaceId}
										onChange={(tasks) => patchForm({ tasks })}
									/>
									<UnattendedToggle
										checked={form.unattended}
										onChange={(unattended) => patchForm({ unattended })}
									/>
								</CardContent>
							</section>
							<Separator className="mx-auto data-[orientation=horizontal]:w-[calc(100%-6rem)]" />
							<section>
								<CardHeader className="pb-3">
									<CardTitle className="text-sm font-semibold">Schedule</CardTitle>
								</CardHeader>
								<CardContent>
									<ScheduleSection
										schedule={form.schedule}
										timezone={form.timezone}
										errors={errors}
										onScheduleChange={(schedule) => patchForm({ schedule })}
										onTimezoneChange={(timezone) => patchForm({ timezone })}
									/>
								</CardContent>
							</section>
							<Separator className="mx-auto data-[orientation=horizontal]:w-[calc(100%-6rem)]" />
							<section>
								<CardHeader className="pb-3">
									<CardTitle className="text-sm font-semibold">Models</CardTitle>
								</CardHeader>
								<CardContent>
									<AutomationModelFields
										searchSpaceId={searchSpaceId}
										value={resolvedModels}
										onChange={(patch) => patchForm({ models: { ...form.models, ...patch } })}
									/>
								</CardContent>
							</section>
							<Separator className="mx-auto data-[orientation=horizontal]:w-[calc(100%-6rem)]" />
							<section>
								<CardHeader className="pb-3">
									<CardTitle className="text-sm font-semibold">Settings</CardTitle>
								</CardHeader>
								<CardContent>
									<AdvancedSection
										execution={form.execution}
										tags={form.tags}
										onExecutionChange={(patch) =>
											patchForm({ execution: { ...form.execution, ...patch } })
										}
										onTagsChange={(tags) => patchForm({ tags })}
									/>
								</CardContent>
							</section>
						</Card>
					</div>

					<div className="lg:col-span-1">
						<Card className="rounded-md border-accent bg-accent/20 lg:sticky lg:top-4">
							<CardHeader className="pb-3">
								<CardTitle className="text-sm font-semibold">Summary</CardTitle>
							</CardHeader>
							<CardContent>
								<BuilderSummary form={form} />
							</CardContent>
						</Card>
					</div>
				</div>
			)}

			{rootError && (
				<Alert variant="destructive">
					<AlertCircle aria-hidden />
					<AlertDescription>{rootError}</AlertDescription>
				</Alert>
			)}

			<div className="flex items-center justify-end gap-2">
				{submitBlocked ? (
					<Tooltip>
						<TooltipTrigger asChild>
							{/* aria-disabled keeps the button focusable so the tooltip is
							    reachable by hover and keyboard; onClick is a no-op. */}
							<Button
								type="button"
								size="sm"
								aria-disabled
								className="cursor-not-allowed opacity-50"
								onClick={(event) => event.preventDefault()}
							>
								{submitLabel}
							</Button>
						</TooltipTrigger>
						<TooltipContent className="max-w-xs">{effectiveDisabledReason}</TooltipContent>
					</Tooltip>
				) : (
					<Button
						type="button"
						size="sm"
						disabled={submitting}
						onClick={() => (activeMode === "json" ? submitJson() : submitForm())}
					>
						{submitting ? (
							<Spinner size="xs" className="mr-2" />
						) : null}
						{submitLabel}
					</Button>
				)}
			</div>
		</div>
	);
}

function extractTriggers(raw: unknown): HydratableTrigger[] {
	if (!Array.isArray(raw)) return [];
	return raw.map((entry) => {
		const obj = entry && typeof entry === "object" ? (entry as Record<string, unknown>) : {};
		return {
			type: typeof obj.type === "string" ? obj.type : "",
			params:
				obj.params && typeof obj.params === "object" ? (obj.params as Record<string, unknown>) : {},
		};
	});
}

function zodIssueList(error: z.ZodError): string[] {
	return error.issues.map((issue) => `${issue.path.join(".") || "(root)"}: ${issue.message}`);
}

function jsonFromAutomation(automation: Automation | undefined): Record<string, unknown> {
	if (!automation) return {};
	return {
		name: automation.name,
		description: automation.description ?? null,
		status: automation.status,
		definition: automation.definition,
	};
}
