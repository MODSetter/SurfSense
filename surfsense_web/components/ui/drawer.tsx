"use client";

import type * as React from "react";
import { Drawer as DrawerPrimitive } from "vaul";

import { cn } from "@/lib/utils";

function Drawer({
	shouldScaleBackground = true,
	...props
}: React.ComponentProps<typeof DrawerPrimitive.Root>) {
	return <DrawerPrimitive.Root shouldScaleBackground={shouldScaleBackground} {...props} />;
}
Drawer.displayName = "Drawer";

const DrawerTrigger = DrawerPrimitive.Trigger;

const DrawerPortal = DrawerPrimitive.Portal;

const DrawerClose = DrawerPrimitive.Close;

function DrawerOverlay({
	className,
	...props
}: React.ComponentProps<typeof DrawerPrimitive.Overlay>) {
	return (
		<DrawerPrimitive.Overlay
			className={cn("fixed inset-0 z-50 bg-black/80", className)}
			{...props}
		/>
	);
}
DrawerOverlay.displayName = DrawerPrimitive.Overlay.displayName;

function DrawerContent({
	className,
	children,
	overlayClassName,
	...props
}: React.ComponentProps<typeof DrawerPrimitive.Content> & {
	overlayClassName?: string;
}) {
	return (
		<DrawerPortal>
			<DrawerOverlay className={overlayClassName} />
			<DrawerPrimitive.Content
				className={cn(
					"fixed inset-x-0 bottom-0 z-50 mt-24 flex h-auto flex-col rounded-t-[10px] border bg-background",
					className
				)}
				{...props}
			>
				{children}
			</DrawerPrimitive.Content>
		</DrawerPortal>
	);
}
DrawerContent.displayName = "DrawerContent";

function DrawerHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
	return <div className={cn("grid gap-1.5 p-4 text-center sm:text-left", className)} {...props} />;
}
DrawerHeader.displayName = "DrawerHeader";

function DrawerFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
	return <div className={cn("mt-auto flex flex-col gap-2 p-4", className)} {...props} />;
}
DrawerFooter.displayName = "DrawerFooter";

function DrawerTitle({ className, ...props }: React.ComponentProps<typeof DrawerPrimitive.Title>) {
	return (
		<DrawerPrimitive.Title
			className={cn("text-lg font-semibold leading-none tracking-tight", className)}
			{...props}
		/>
	);
}
DrawerTitle.displayName = DrawerPrimitive.Title.displayName;

function DrawerDescription({
	className,
	...props
}: React.ComponentProps<typeof DrawerPrimitive.Description>) {
	return (
		<DrawerPrimitive.Description
			className={cn("text-sm text-muted-foreground", className)}
			{...props}
		/>
	);
}
DrawerDescription.displayName = DrawerPrimitive.Description.displayName;

function DrawerHandle({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
	return (
		<div
			className={cn("mx-auto mt-4 h-1.5 w-12 rounded-full bg-muted-foreground/40", className)}
			{...props}
		/>
	);
}
DrawerHandle.displayName = "DrawerHandle";

export {
	Drawer,
	DrawerPortal,
	DrawerOverlay,
	DrawerTrigger,
	DrawerClose,
	DrawerContent,
	DrawerHeader,
	DrawerFooter,
	DrawerTitle,
	DrawerDescription,
	DrawerHandle,
};
