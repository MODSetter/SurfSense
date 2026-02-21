"use client";

import { useEquationElement, useEquationInput } from "@platejs/math/react";
import { RadicalIcon } from "lucide-react";
import type { TEquationElement } from "platejs";
import { PlateElement, type PlateElementProps, useSelected } from "platejs/react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function EquationElement({ children, ...props }: PlateElementProps<TEquationElement>) {
	const element = props.element;
	const selected = useSelected();
	const katexRef = React.useRef<HTMLDivElement | null>(null);
	const [isEditing, setIsEditing] = React.useState(false);

	useEquationElement({
		element,
		katexRef,
		options: {
			displayMode: true,
			throwOnError: false,
		},
	});

	const {
		props: inputProps,
		ref: inputRef,
		onDismiss,
		onSubmit,
	} = useEquationInput({
		isInline: false,
		open: isEditing,
		onClose: () => setIsEditing(false),
	});

	return (
		<PlateElement
			{...props}
			className={cn(
				"my-3 rounded-md py-2",
				selected && "ring-2 ring-ring ring-offset-2",
				props.className
			)}
		>
			<div
				className="flex cursor-pointer items-center justify-center"
				contentEditable={false}
				onDoubleClick={() => setIsEditing(true)}
			>
				{element.texExpression ? (
					<div ref={katexRef} className="text-center" />
				) : (
					<div className="flex items-center gap-2 text-sm text-muted-foreground">
						<RadicalIcon className="size-4" />
						<span>Add an equation</span>
					</div>
				)}
			</div>

			{isEditing && (
				<div className="mt-2 rounded-md border bg-muted/50 p-2" contentEditable={false}>
					<textarea
						ref={inputRef}
						className="w-full resize-none rounded border-none bg-transparent p-2 font-mono text-sm outline-none"
						placeholder="E = mc^2"
						rows={3}
						{...inputProps}
					/>
					<div className="mt-1 flex justify-end gap-1">
						<button
							className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent"
							onClick={onDismiss}
							type="button"
						>
							Cancel
						</button>
						<button
							className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground hover:bg-primary/90"
							onClick={onSubmit}
							type="button"
						>
							Done
						</button>
					</div>
				</div>
			)}

			{children}
		</PlateElement>
	);
}

export function InlineEquationElement({ children, ...props }: PlateElementProps<TEquationElement>) {
	const element = props.element;
	const selected = useSelected();
	const katexRef = React.useRef<HTMLDivElement | null>(null);
	const [isEditing, setIsEditing] = React.useState(false);

	useEquationElement({
		element,
		katexRef,
		options: {
			displayMode: false,
			throwOnError: false,
		},
	});

	const {
		props: inputProps,
		ref: inputRef,
		onDismiss,
		onSubmit,
	} = useEquationInput({
		isInline: true,
		open: isEditing,
		onClose: () => setIsEditing(false),
	});

	return (
		<PlateElement
			{...props}
			as="span"
			className={cn("inline rounded-sm px-0.5", selected && "bg-brand/15", props.className)}
		>
			<span
				className="cursor-pointer"
				contentEditable={false}
				onDoubleClick={() => setIsEditing(true)}
			>
				{element.texExpression ? (
					<span ref={katexRef} />
				) : (
					<span className="text-sm text-muted-foreground">
						<RadicalIcon className="inline size-3.5" />
					</span>
				)}
			</span>

			{isEditing && (
				<span
					className="absolute z-50 mt-1 rounded-md border bg-popover p-2 shadow-md"
					contentEditable={false}
				>
					<textarea
						ref={inputRef}
						className="w-48 resize-none rounded border-none bg-transparent p-1 font-mono text-sm outline-none"
						placeholder="x^2"
						rows={1}
						{...inputProps}
					/>
					<span className="mt-1 flex justify-end gap-1">
						<button
							className="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent"
							onClick={onDismiss}
							type="button"
						>
							Cancel
						</button>
						<button
							className="rounded bg-primary px-2 py-0.5 text-xs text-primary-foreground hover:bg-primary/90"
							onClick={onSubmit}
							type="button"
						>
							Done
						</button>
					</span>
				</span>
			)}

			{children}
		</PlateElement>
	);
}
