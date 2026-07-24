"use client";
import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface FieldProps {
	label?: string;
	htmlFor?: string;
	hint?: string;
	error?: string;
	required?: boolean;
	className?: string;
	children: ReactNode;
}

/**
 * Label + control + (hint | inline error) stack shared by every builder
 * section. Keeps spacing and error styling consistent so individual sections
 * stay focused on their inputs.
 */
export function Field({ label, htmlFor, hint, error, required, className, children }: FieldProps) {
	return (
		<div className={cn("space-y-1.5", className)}>
			{label && (
				<Label htmlFor={htmlFor} className="text-xs font-medium text-foreground">
					{label}
					{required && <span className="text-muted-foreground">*</span>}
				</Label>
			)}
			{children}
			{error ? (
				<p className="flex items-center gap-1 text-xs text-destructive">
					<AlertCircle className="h-3 w-3 shrink-0" aria-hidden />
					{error}
				</p>
			) : hint ? (
				<p className="text-xs text-muted-foreground">{hint}</p>
			) : null}
		</div>
	);
}
