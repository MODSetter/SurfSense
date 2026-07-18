"use client";

import { ChevronDown } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { FormField } from "@/lib/playground/json-schema";
import { cn } from "@/lib/utils";

export interface FieldOption {
	label: string;
	value: string;
}

type FieldOptionsResolver = (field: FormField) => FieldOption[] | undefined;

interface SchemaFormProps {
	fields: FormField[];
	values: Record<string, unknown>;
	onChange: (name: string, value: unknown) => void;
	disabled?: boolean;
	getFieldOptions?: FieldOptionsResolver;
	/** Field names flagged by a 422 response, shown with error styling. */
	fieldErrors?: Record<string, string>;
}

function FieldControl({
	field,
	value,
	onChange,
	disabled,
	invalid,
	options,
}: {
	field: FormField;
	value: unknown;
	onChange: (value: unknown) => void;
	disabled?: boolean;
	invalid?: boolean;
	options?: FieldOption[];
}) {
	const id = `field-${field.name}`;

	if (field.kind === "boolean") {
		return (
			<Switch id={id} checked={Boolean(value)} onCheckedChange={onChange} disabled={disabled} />
		);
	}

	if (field.kind === "enum" && field.enumValues) {
		return (
			<Select
				value={value ? String(value) : undefined}
				onValueChange={onChange}
				disabled={disabled}
			>
				<SelectTrigger id={id} className={cn("w-full", invalid && "border-destructive")}>
					<SelectValue placeholder="Select…" />
				</SelectTrigger>
				<SelectContent>
					{field.enumValues.map((option) => (
						<SelectItem key={option} value={option}>
							{option}
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		);
	}

	if (options) {
		return (
			<Select
				value={value ? String(value) : options[0]?.value}
				onValueChange={onChange}
				disabled={disabled}
			>
				<SelectTrigger id={id} className={cn("w-full", invalid && "border-destructive")}>
					<SelectValue placeholder="Select…" />
				</SelectTrigger>
				<SelectContent>
					{options.map((option) => (
						<SelectItem key={option.value} value={option.value}>
							{option.label} ({option.value})
						</SelectItem>
					))}
				</SelectContent>
			</Select>
		);
	}

	if (field.kind === "string_array") {
		return (
			<Textarea
				id={id}
				value={String(value ?? "")}
				onChange={(e) => onChange(e.target.value)}
				placeholder="One value per line"
				disabled={disabled}
				rows={4}
				className={cn("font-mono text-xs", invalid && "border-destructive")}
			/>
		);
	}

	if (field.kind === "integer" || field.kind === "number") {
		return (
			<Input
				id={id}
				type="number"
				value={value === undefined || value === null ? "" : String(value)}
				min={field.minimum}
				max={field.maximum}
				step={field.kind === "integer" ? 1 : "any"}
				onChange={(e) => onChange(e.target.value)}
				disabled={disabled}
				className={cn(invalid && "border-destructive")}
			/>
		);
	}

	return (
		<Input
			id={id}
			type="text"
			value={String(value ?? "")}
			onChange={(e) => onChange(e.target.value)}
			disabled={disabled}
			className={cn(invalid && "border-destructive")}
		/>
	);
}

function FieldRow({
	field,
	value,
	onChange,
	disabled,
	error,
	options,
}: {
	field: FormField;
	value: unknown;
	onChange: (value: unknown) => void;
	disabled?: boolean;
	error?: string;
	options?: FieldOption[];
}) {
	return (
		<div className="space-y-1.5">
			<div className="flex items-center gap-2">
				<Label htmlFor={`field-${field.name}`} className="text-sm font-medium">
					{field.title}
				</Label>
				<Badge
					variant={field.required ? "destructive" : "secondary"}
					className="px-1.5 py-0 text-[10px]"
				>
					{field.required ? "required" : "optional"}
				</Badge>
			</div>
			{field.description && <p className="text-xs text-muted-foreground">{field.description}</p>}
			<FieldControl
				field={field}
				value={value}
				onChange={onChange}
				disabled={disabled}
				invalid={!!error}
				options={options}
			/>
			{error && <p className="text-xs text-destructive">{error}</p>}
		</div>
	);
}

export function SchemaForm({
	fields,
	values,
	onChange,
	disabled,
	getFieldOptions,
	fieldErrors,
}: SchemaFormProps) {
	const [showAdvanced, setShowAdvanced] = useState(false);

	const { primary, advanced } = useMemo(() => {
		const primaryFields = fields.filter((f) => f.required);
		const advancedFields = fields.filter((f) => !f.required);
		return { primary: primaryFields, advanced: advancedFields };
	}, [fields]);

	return (
		<div className="space-y-5">
			{primary.map((field) => (
				<FieldRow
					key={field.name}
					field={field}
					value={values[field.name]}
					onChange={(value) => onChange(field.name, value)}
					disabled={disabled}
					error={fieldErrors?.[field.name]}
					options={getFieldOptions?.(field)}
				/>
			))}

			{advanced.length > 0 && (
				<div className="rounded-md border border-border/60">
					<button
						type="button"
						onClick={() => setShowAdvanced((prev) => !prev)}
						className="flex w-full items-center justify-between px-4 py-2.5 text-sm font-medium hover:bg-muted/30 transition-colors"
						aria-expanded={showAdvanced}
					>
						<span>Advanced ({advanced.length})</span>
						<ChevronDown
							className={cn(
								"h-4 w-4 text-muted-foreground transition-transform",
								showAdvanced && "rotate-180"
							)}
						/>
					</button>
					{showAdvanced && (
						<div className="space-y-5 border-t border-border/60 px-4 py-4">
							{advanced.map((field) => (
								<FieldRow
									key={field.name}
									field={field}
									value={values[field.name]}
									onChange={(value) => onChange(field.name, value)}
									disabled={disabled}
									error={fieldErrors?.[field.name]}
									options={getFieldOptions?.(field)}
								/>
							))}
						</div>
					)}
				</div>
			)}
		</div>
	);
}
