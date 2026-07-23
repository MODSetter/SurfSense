"use client";

import {
	ChevronLeft,
	ChevronRight,
	LayoutGrid,
	Settings2,
	Unplug,
	Upload,
	Wrench,
} from "lucide-react";
import Image from "next/image";
import { type ReactNode, useCallback, useRef, useState } from "react";
import type {
	ConnectorTypeRow,
} from "@/components/assistant-ui/connector-popup/constants/connector-constants";
import { Button } from "@/components/ui/button";
import {
	Drawer,
	DrawerContent,
	DrawerHandle,
	DrawerHeader,
	DrawerTitle,
	DrawerTrigger,
} from "@/components/ui/drawer";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import {
	CONNECTOR_TOOL_ICON_PATHS,
	getToolDisplayName,
	getToolIcon,
} from "@/contracts/enums/toolIcons";
import { cn } from "@/lib/utils";

/** Minimal shape of a grouped agent-tool section (mirrors thread.tsx). */
export interface ToolGroupView {
	label: string;
	tools: { name: string }[];
	connectorIcon?: string;
}

interface ComposerAddMenuDrawerProps {
	/** The `+` button; rendered as the drawer trigger. */
	trigger: ReactNode;
	onUploadFiles: () => void;
	/** Connected connectors, one row per type (see `groupConnectorsByType`). */
	connectorRows: ConnectorTypeRow[];
	/** Open a connector's manage view (deep-links via importConnectorRequestAtom). */
	onSelectConnector: (row: ConnectorTypeRow) => void;
	/** Navigate to the full connectors catalog. */
	onBrowseConnectors: () => void;
	regularToolGroups: ToolGroupView[];
	connectorToolGroups: ToolGroupView[];
	otherToolGroup?: ToolGroupView;
	disabledToolsSet: Set<string>;
	onToggleTool: (name: string) => void;
	onToggleToolGroup: (names: string[]) => void;
	/** True while the tool list is still loading (shows a skeleton). */
	toolsLoading: boolean;
}

/**
 * Mobile "+" menu. A single vaul drawer that behaves like a flat list at the
 * root and drills into submenus in place (each level replaces the previous,
 * with a back button) rather than nesting overlays — the touch-friendly
 * equivalent of the desktop dropdown submenus. Screen state is a small push/pop
 * stack; closing the drawer resets it to the root.
 */
type Screen =
	| { kind: "root" }
	| { kind: "connectors" }
	| { kind: "tools" }
	| { kind: "toolGroup"; label: string };

const ROW = "flex w-full items-center gap-3 px-4 py-3 text-sm hover:bg-accent hover:text-accent-foreground transition-colors";

export function ComposerAddMenuDrawer({
	trigger,
	onUploadFiles,
	connectorRows,
	onSelectConnector,
	onBrowseConnectors,
	regularToolGroups,
	connectorToolGroups,
	otherToolGroup,
	disabledToolsSet,
	onToggleTool,
	onToggleToolGroup,
	toolsLoading,
}: ComposerAddMenuDrawerProps) {
	const [open, setOpen] = useState(false);
	const [stack, setStack] = useState<Screen[]>([{ kind: "root" }]);
	// Slide direction: forward on push, back on pop — drives the enter animation.
	const dirRef = useRef<"forward" | "back">("forward");
	const current = stack[stack.length - 1];

	const push = useCallback((screen: Screen) => {
		dirRef.current = "forward";
		setStack((prev) => [...prev, screen]);
	}, []);
	const pop = useCallback(() => {
		dirRef.current = "back";
		setStack((prev) => (prev.length > 1 ? prev.slice(0, -1) : prev));
	}, []);

	const handleOpenChange = useCallback((next: boolean) => {
		setOpen(next);
		// Reset to root when closed so the next open starts fresh.
		if (!next) {
			dirRef.current = "forward";
			setStack([{ kind: "root" }]);
		}
	}, []);

	const close = useCallback(() => handleOpenChange(false), [handleOpenChange]);

	const title =
		current.kind === "connectors"
			? "MCP Connectors"
			: current.kind === "tools"
				? "Manage Tools"
				: current.kind === "toolGroup"
					? current.label
					: "Add";

	const renderToolRow = (name: string) => {
		const isDisabled = disabledToolsSet.has(name);
		const ToolIcon = getToolIcon(name);
		return (
			<div key={name} className={ROW}>
				<ToolIcon className="size-4 shrink-0 text-muted-foreground" />
				<span className="min-w-0 flex-1 truncate font-medium">{getToolDisplayName(name)}</span>
				<Switch
					checked={!isDisabled}
					onCheckedChange={() => onToggleTool(name)}
					className="shrink-0"
				/>
			</div>
		);
	};

	const renderBody = () => {
		if (current.kind === "root") {
			return (
				<>
					<button
						type="button"
						className={ROW}
						onClick={() => {
							onUploadFiles();
							close();
						}}
					>
						<Upload className="size-4 shrink-0 text-muted-foreground" />
						<span className="flex-1 text-left">Upload Files</span>
					</button>
					<button
						type="button"
						className={ROW}
						onClick={() => push({ kind: "connectors" })}
					>
						<Unplug className="size-4 shrink-0 text-muted-foreground" />
						<span className="flex-1 text-left">MCP Connectors</span>
						<ChevronRight className="size-4 shrink-0 text-muted-foreground" />
					</button>
					<button type="button" className={ROW} onClick={() => push({ kind: "tools" })}>
						<Settings2 className="size-4 shrink-0 text-muted-foreground" />
						<span className="flex-1 text-left">Manage Tools</span>
						<ChevronRight className="size-4 shrink-0 text-muted-foreground" />
					</button>
				</>
			);
		}

		if (current.kind === "connectors") {
			return (
				<>
					{connectorRows.length === 0 ? (
						<p className="px-4 py-6 text-center text-sm text-muted-foreground">
							No connectors yet.
						</p>
					) : (
						connectorRows.map((row) => (
							<button
								type="button"
								key={row.type}
								className={ROW}
								onClick={() => {
									onSelectConnector(row);
									close();
								}}
							>
								{getConnectorIcon(row.type, "size-4 shrink-0 text-muted-foreground")}
								<span className="min-w-0 flex-1 truncate text-left">{row.title}</span>
								{row.accountCount > 1 ? (
									<span className="shrink-0 text-xs text-muted-foreground">{row.accountCount}</span>
								) : null}
							</button>
						))
					)}
					<Separator className="my-1" />
					<button
						type="button"
						className={ROW}
						onClick={() => {
							onBrowseConnectors();
							close();
						}}
					>
						<LayoutGrid className="size-4 shrink-0 text-muted-foreground" />
						<span className="flex-1 text-left">Browse all connectors</span>
					</button>
				</>
			);
		}

		if (current.kind === "toolGroup") {
			const group = connectorToolGroups.find((g) => g.label === current.label);
			return <>{group?.tools.map((t) => renderToolRow(t.name))}</>;
		}

		// current.kind === "tools"
		if (toolsLoading) {
			return (
				<div className="px-4 pt-3 pb-2">
					<Skeleton className="h-3 w-16 mb-2" />
					{["t1", "t2", "t3", "t4"].map((k) => (
						<div key={k} className="flex items-center gap-3 py-2">
							<Skeleton className="size-4 rounded shrink-0" />
							<Skeleton className="h-3.5 flex-1" />
							<Skeleton className="h-5 w-9 rounded-full shrink-0" />
						</div>
					))}
				</div>
			);
		}

		return (
			<>
				{regularToolGroups.map((group) => (
					<div key={group.label}>
						<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground font-semibold select-none">
							{group.label}
						</div>
						{group.tools.map((t) => renderToolRow(t.name))}
					</div>
				))}
				{connectorToolGroups.length > 0 && (
					<div>
						<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground font-semibold select-none">
							Connector Actions
						</div>
						{connectorToolGroups.map((group) => {
							const iconInfo = CONNECTOR_TOOL_ICON_PATHS[group.connectorIcon ?? ""];
							const toolNames = group.tools.map((t) => t.name);
							const allDisabled = toolNames.every((n) => disabledToolsSet.has(n));
							return (
								<div key={group.label} className={ROW}>
									<button
										type="button"
										className="flex min-w-0 flex-1 items-center gap-3"
										onClick={() => push({ kind: "toolGroup", label: group.label })}
									>
										{iconInfo ? (
											<Image
												src={iconInfo.src}
												alt={iconInfo.alt}
												width={18}
												height={18}
												className="size-[18px] shrink-0 select-none pointer-events-none"
												draggable={false}
											/>
										) : (
											<Wrench className="size-4 shrink-0 text-muted-foreground" />
										)}
										<span className="min-w-0 flex-1 truncate text-left font-medium">
											{group.label}
										</span>
										<ChevronRight className="size-4 shrink-0 text-muted-foreground" />
									</button>
									<Switch
										checked={!allDisabled}
										onCheckedChange={() => onToggleToolGroup(toolNames)}
										className="shrink-0"
									/>
								</div>
							);
						})}
					</div>
				)}
				{otherToolGroup && (
					<div>
						<div className="px-4 pt-3 pb-1 text-xs text-muted-foreground font-semibold select-none">
							{otherToolGroup.label}
						</div>
						{otherToolGroup.tools.map((t) => renderToolRow(t.name))}
					</div>
				)}
			</>
		);
	};

	return (
		<Drawer open={open} onOpenChange={handleOpenChange} shouldScaleBackground={false}>
			<DrawerTrigger asChild>{trigger}</DrawerTrigger>
			<DrawerContent className="h-[85vh] max-h-[85vh] z-80" overlayClassName="z-80">
				<DrawerHandle />
				<DrawerHeader className="flex flex-row items-center gap-1 px-2 pb-2 pt-1">
					{stack.length > 1 ? (
						<Button
							type="button"
							variant="ghost"
							size="icon"
							className="size-9 shrink-0"
							onClick={pop}
							aria-label="Back"
						>
							<ChevronLeft className="size-5" />
						</Button>
					) : (
						<span className="size-9 shrink-0" aria-hidden />
					)}
					<DrawerTitle className="flex-1 text-center text-base font-semibold">{title}</DrawerTitle>
					<span className="size-9 shrink-0" aria-hidden />
				</DrawerHeader>
				<div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin pb-6">
					<div
						key={current.kind === "toolGroup" ? `toolGroup:${current.label}` : current.kind}
						className={cn(
							"animate-in fade-in-0 duration-200",
							dirRef.current === "forward" ? "slide-in-from-right-4" : "slide-in-from-left-4"
						)}
					>
						{renderBody()}
					</div>
				</div>
			</DrawerContent>
		</Drawer>
	);
}
