"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import { memo, useId } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectLabel,
	SelectSeparator,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
	type EligibleModelKind,
	type EligibleModelOption,
	useAutomationEligibleModels,
} from "@/hooks/use-automation-eligible-models";
import { getProviderIcon } from "@/lib/provider-icons";
import { Field } from "./form-field";

export interface AutomationModelSelection {
	agentLlmId: number;
	imageConfigId: number;
	visionConfigId: number;
}

interface AutomationModelFieldsProps {
	/** Resolved (effective) ids — never `0` once defaults are seeded. */
	value: AutomationModelSelection;
	onChange: (patch: Partial<AutomationModelSelection>) => void;
	searchSpaceId: number;
	errors?: Partial<Record<keyof AutomationModelSelection, string>>;
}

/**
 * Three eligible-only model pickers (Agent LLM / Image / Vision) for the
 * automation builder + chat approval card. Options come from
 * {@link useAutomationEligibleModels} (premium globals + BYOK only); selection
 * is validated + snapshotted onto `definition.models` at create time.
 */
export function AutomationModelFields({
	value,
	onChange,
	searchSpaceId,
	errors,
}: AutomationModelFieldsProps) {
	const { llm, image, vision, isLoading } = useAutomationEligibleModels();
	const rolesHref = `/dashboard/${searchSpaceId}/search-space-settings/roles`;

	return (
		<div className="flex flex-col gap-4">
			<ModelSelectField
				label="Agent model"
				kind={llm}
				value={value.agentLlmId}
				isLoading={isLoading}
				rolesHref={rolesHref}
				error={errors?.agentLlmId}
				onChange={(id) => onChange({ agentLlmId: id })}
			/>
			<ModelSelectField
				label="Image model"
				kind={image}
				value={value.imageConfigId}
				isLoading={isLoading}
				rolesHref={rolesHref}
				error={errors?.imageConfigId}
				onChange={(id) => onChange({ imageConfigId: id })}
			/>
			<ModelSelectField
				label="Vision model"
				kind={vision}
				value={value.visionConfigId}
				isLoading={isLoading}
				rolesHref={rolesHref}
				error={errors?.visionConfigId}
				onChange={(id) => onChange({ visionConfigId: id })}
			/>
		</div>
	);
}

interface ModelSelectFieldProps {
	label: string;
	kind: EligibleModelKind;
	value: number;
	isLoading: boolean;
	rolesHref: string;
	error?: string;
	onChange: (id: number) => void;
}

const ModelSelectField = memo(function ModelSelectField({
	label,
	kind,
	value,
	isLoading,
	rolesHref,
	error,
	onChange,
}: ModelSelectFieldProps) {
	const triggerId = useId();

	if (isLoading) {
		return (
			<Field label={label}>
				<Skeleton className="h-9 w-full" />
			</Field>
		);
	}

	if (kind.options.length === 0) {
		return (
			<Field label={label}>
				<Alert>
					<TriangleAlert aria-hidden />
					<AlertTitle>No eligible models</AlertTitle>
					<AlertDescription>
						Automations need a premium or your own (BYOK) model. Set one up in{" "}
						<Link href={rolesHref} className="font-medium underline underline-offset-2">
							role settings
						</Link>
						.
					</AlertDescription>
				</Alert>
			</Field>
		);
	}

	const premium = kind.options.filter((o) => !o.isBYOK);
	const byok = kind.options.filter((o) => o.isBYOK);
	const selected = value ? kind.byId.get(value) : undefined;

	return (
		<Field label={label} htmlFor={triggerId} error={error}>
			<Select value={value ? String(value) : undefined} onValueChange={(v) => onChange(Number(v))}>
				<SelectTrigger
					id={triggerId}
					aria-label={label}
					aria-invalid={error ? true : undefined}
					className="w-full"
				>
					{selected ? (
						<span className="flex items-center gap-2">
							{getProviderIcon(selected.provider)}
							<span className="truncate">{selected.name}</span>
						</span>
					) : (
						<SelectValue placeholder="Select a model" />
					)}
				</SelectTrigger>
				<SelectContent>
					{premium.length > 0 ? (
						<SelectGroup>
							<SelectLabel>Premium</SelectLabel>
							{premium.map((option) => (
								<ModelOption key={option.id} option={option} badge="Premium" />
							))}
						</SelectGroup>
					) : null}
					{premium.length > 0 && byok.length > 0 ? <SelectSeparator /> : null}
					{byok.length > 0 ? (
						<SelectGroup>
							<SelectLabel>Your models</SelectLabel>
							{byok.map((option) => (
								<ModelOption key={option.id} option={option} badge="BYOK" />
							))}
						</SelectGroup>
					) : null}
				</SelectContent>
			</Select>
		</Field>
	);
});

function ModelOption({
	option,
	badge,
}: {
	option: EligibleModelOption;
	badge: "Premium" | "BYOK";
}) {
	return (
		<SelectItem value={String(option.id)} description={option.modelName}>
			<span className="flex items-center gap-2">
				{getProviderIcon(option.provider)}
				<span className="truncate">{option.name}</span>
				<Badge variant={badge === "Premium" ? "secondary" : "outline"}>{badge}</Badge>
			</span>
		</SelectItem>
	);
}
