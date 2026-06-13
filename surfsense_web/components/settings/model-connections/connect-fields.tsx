import { Eye, EyeOff } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

interface ApiBaseUrlFieldProps {
	value: string;
	onChange: (value: string) => void;
	/** Placeholder, typically the provider's prefilled default base URL. */
	placeholder?: string;
	hint?: ReactNode;
}

/** Shared API Base URL input. The prefilled default is passed in via `value`. */
export function ApiBaseUrlField({ value, onChange, placeholder, hint }: ApiBaseUrlFieldProps) {
	return (
		<div className="flex flex-col gap-2">
			<Label>API Base URL</Label>
			<Input
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder || "https://api.example.com/v1"}
			/>
			{hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
		</div>
	);
}

interface ApiKeyFieldProps {
	value: string;
	onChange: (value: string) => void;
	label?: string;
	placeholder?: string;
}

/** Shared masked API Key input. */
export function ApiKeyField({
	value,
	onChange,
	label = "API Key",
	placeholder = "API key",
}: ApiKeyFieldProps) {
	const [showApiKey, setShowApiKey] = useState(false);

	return (
		<div className="flex flex-col gap-2">
			<Label>{label}</Label>
			<div className="relative">
				<Input
					value={value}
					onChange={(event) => onChange(event.target.value)}
					placeholder={placeholder}
					type={showApiKey ? "text" : "password"}
					className="pr-11"
				/>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
					onClick={() => setShowApiKey((current) => !current)}
					disabled={!value}
					aria-label={showApiKey ? "Hide API key" : "Show API key"}
				>
					{showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
				</Button>
			</div>
		</div>
	);
}

interface ConnectFormFooterProps {
	onCancel: () => void;
	onSubmit: () => void;
	canSubmit: boolean;
	isPending: boolean;
}

/** Shared Cancel / Connect footer for every provider connect form. */
export function ConnectFormFooter({
	onCancel,
	onSubmit,
	canSubmit,
	isPending,
}: ConnectFormFooterProps) {
	return (
		<DialogFooter className="shrink-0 border-t bg-popover px-6 py-4">
			<Button variant="secondary" onClick={onCancel}>
				Cancel
			</Button>
			<Button
				onClick={onSubmit}
				disabled={isPending || !canSubmit}
				className="relative min-w-[96px]"
			>
				<span className={isPending ? "opacity-0" : ""}>Connect</span>
				{isPending ? <Spinner size="sm" className="absolute" /> : null}
			</Button>
		</DialogFooter>
	);
}
