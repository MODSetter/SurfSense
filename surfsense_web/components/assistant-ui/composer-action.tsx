import { AssistantIf, ComposerPrimitive, useAssistantState } from "@assistant-ui/react";
import { useAtomValue } from "jotai";
import {
	AlertCircle,
	ArrowUpIcon,
	ChevronRightIcon,
	Loader2,
	Plug2,
	Plus,
	SquareIcon,
} from "lucide-react";
import type { FC } from "react";
import { useCallback, useMemo, useRef, useState } from "react";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
	newLLMConfigsAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { ComposerAddAttachment } from "@/components/assistant-ui/attachment";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { cn } from "@/lib/utils";

const ConnectorIndicator: FC = () => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { connectors, isLoading: connectorsLoading } = useSearchSourceConnectors(
		false,
		searchSpaceId ? Number(searchSpaceId) : undefined
	);
	const { data: documentTypeCounts, isLoading: documentTypesLoading } =
		useAtomValue(documentTypeCountsAtom);
	const [isOpen, setIsOpen] = useState(false);
	const closeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

	const isLoading = connectorsLoading || documentTypesLoading;

	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([_, count]) => count > 0)
		: [];

	// Count only active connectors (matching what's shown in the Active tab)
	const activeConnectorsCount = connectors.length;
	const hasConnectors = activeConnectorsCount > 0;
	const hasSources = hasConnectors || activeDocumentTypes.length > 0;

	const handleMouseEnter = useCallback(() => {
		// Clear any pending close timeout
		if (closeTimeoutRef.current) {
			clearTimeout(closeTimeoutRef.current);
			closeTimeoutRef.current = null;
		}
		setIsOpen(true);
	}, []);

	const handleMouseLeave = useCallback(() => {
		// Delay closing by 150ms for better UX
		closeTimeoutRef.current = setTimeout(() => {
			setIsOpen(false);
		}, 150);
	}, []);

	if (!searchSpaceId) return null;

	return (
		<Popover open={isOpen} onOpenChange={setIsOpen}>
			<PopoverTrigger asChild>
				<button
					type="button"
					className={cn(
						"size-[34px] rounded-full p-1 flex items-center justify-center transition-colors relative",
						"hover:bg-muted-foreground/15 dark:hover:bg-muted-foreground/30",
						"outline-none focus:outline-none focus-visible:outline-none",
						"border-0 ring-0 focus:ring-0 shadow-none focus:shadow-none",
						"data-[state=open]:bg-transparent data-[state=open]:shadow-none data-[state=open]:ring-0",
						"text-muted-foreground"
					)}
					aria-label={
						hasConnectors
							? `View ${activeConnectorsCount} active connectors`
							: "Add your first connector"
					}
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
				>
					{isLoading ? (
						<Loader2 className="size-4 animate-spin" />
					) : (
						<>
							<Plug2 className="size-4" />
							{activeConnectorsCount > 0 && (
								<span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-medium rounded-full bg-primary text-primary-foreground shadow-sm">
									{activeConnectorsCount > 99 ? "99+" : activeConnectorsCount}
								</span>
							)}
						</>
					)}
				</button>
			</PopoverTrigger>
			<PopoverContent
				side="bottom"
				align="start"
				className="w-64 p-3"
				onMouseEnter={handleMouseEnter}
				onMouseLeave={handleMouseLeave}
			>
				{hasSources ? (
					<div className="space-y-3">
						{activeConnectorsCount > 0 && (
							<div className="flex items-center justify-between">
								<p className="text-xs font-medium text-muted-foreground">Active Connectors</p>
								<span className="text-xs font-medium bg-muted px-1.5 py-0.5 rounded">
									{activeConnectorsCount}
								</span>
							</div>
						)}
						{activeConnectorsCount > 0 && (
							<div className="flex flex-wrap gap-2">
								{connectors.map((connector) => (
									<div
										key={`connector-${connector.id}`}
										className="flex items-center gap-1.5 rounded-md bg-muted/80 px-2.5 py-1.5 text-xs border border-border/50"
									>
										{getConnectorIcon(connector.connector_type, "size-3.5")}
										<span className="truncate max-w-[100px]">{connector.name}</span>
									</div>
								))}
							</div>
						)}
						{activeDocumentTypes.length > 0 && (
							<>
								{activeConnectorsCount > 0 && (
									<div className="pt-2 border-t border-border/50">
										<p className="text-xs font-medium text-muted-foreground mb-2">Documents</p>
									</div>
								)}
								<div className="flex flex-wrap gap-2">
									{activeDocumentTypes.map(([docType, count]) => (
										<div
											key={docType}
											className="flex items-center gap-1.5 rounded-md bg-muted/80 px-2.5 py-1.5 text-xs border border-border/50"
										>
											{getConnectorIcon(docType, "size-3.5")}
											<span className="truncate max-w-[100px]">
												{getDocumentTypeLabel(docType)}
											</span>
											<span className="flex items-center justify-center min-w-[18px] h-[18px] px-1 text-[10px] font-medium rounded-full bg-primary/10 text-primary">
												{count > 999 ? "999+" : count}
											</span>
										</div>
									))}
								</div>
							</>
						)}
						<div className="pt-1 border-t border-border/50">
							<button
								type="button"
								className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
								onClick={() => {
									/* Connector popup should be opened via the connector indicator button */
								}}
							>
								<Plus className="size-3" />
								Add more sources
								<ChevronRightIcon className="size-3" />
							</button>
						</div>
					</div>
				) : (
					<div className="space-y-2">
						<p className="text-sm font-medium">No sources yet</p>
						<p className="text-xs text-muted-foreground">
							Add documents or connect data sources to enhance search results.
						</p>
						<button
							type="button"
							className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors mt-1"
							onClick={() => {
								/* Connector popup should be opened via the connector indicator button */
							}}
						>
							<Plus className="size-3" />
							Add Connector
						</button>
					</div>
				)}
			</PopoverContent>
		</Popover>
	);
};

export const ComposerAction: FC = () => {
	// Check if any attachments are still being processed (running AND progress < 100)
	// When progress is 100, processing is done but waiting for send()
	const hasProcessingAttachments = useAssistantState(({ composer }) =>
		composer.attachments?.some((att) => {
			const status = att.status;
			if (status?.type !== "running") return false;
			const progress = (status as { type: "running"; progress?: number }).progress;
			return progress === undefined || progress < 100;
		})
	);

	// Check if composer text is empty
	const isComposerEmpty = useAssistantState(({ composer }) => {
		const text = composer.text?.trim() || "";
		return text.length === 0;
	});

	// Check if a model is configured
	const { data: userConfigs } = useAtomValue(newLLMConfigsAtom);
	const { data: globalConfigs } = useAtomValue(globalNewLLMConfigsAtom);
	const { data: preferences } = useAtomValue(llmPreferencesAtom);

	const hasModelConfigured = useMemo(() => {
		if (!preferences) return false;
		const agentLlmId = preferences.agent_llm_id;
		if (agentLlmId === null || agentLlmId === undefined) return false;

		// Check if the configured model actually exists
		if (agentLlmId < 0) {
			return globalConfigs?.some((c) => c.id === agentLlmId) ?? false;
		}
		return userConfigs?.some((c) => c.id === agentLlmId) ?? false;
	}, [preferences, globalConfigs, userConfigs]);

	const isSendDisabled = hasProcessingAttachments || isComposerEmpty || !hasModelConfigured;

	return (
		<div className="aui-composer-action-wrapper relative mx-2 mb-2 flex items-center justify-between">
			<div className="flex items-center gap-1">
				<ComposerAddAttachment />
				<ConnectorIndicator />
			</div>

			{/* Show processing indicator when attachments are being processed */}
			{hasProcessingAttachments && (
				<div className="flex items-center gap-1.5 text-muted-foreground text-xs">
					<Loader2 className="size-3 animate-spin" />
					<span>Processing...</span>
				</div>
			)}

			{/* Show warning when no model is configured */}
			{!hasModelConfigured && !hasProcessingAttachments && (
				<div className="flex items-center gap-1.5 text-amber-600 dark:text-amber-400 text-xs">
					<AlertCircle className="size-3" />
					<span>Select a model</span>
				</div>
			)}

			<AssistantIf condition={({ thread }) => !thread.isRunning}>
				<ComposerPrimitive.Send asChild disabled={isSendDisabled}>
					<TooltipIconButton
						tooltip={
							!hasModelConfigured
								? "Please select a model from the header to start chatting"
								: hasProcessingAttachments
									? "Wait for attachments to process"
									: isComposerEmpty
										? "Enter a message to send"
										: "Send message"
						}
						side="bottom"
						type="submit"
						variant="default"
						size="icon"
						className={cn(
							"aui-composer-send size-8 rounded-full",
							isSendDisabled && "cursor-not-allowed opacity-50"
						)}
						aria-label="Send message"
						disabled={isSendDisabled}
					>
						<ArrowUpIcon className="aui-composer-send-icon size-4" />
					</TooltipIconButton>
				</ComposerPrimitive.Send>
			</AssistantIf>

			<AssistantIf condition={({ thread }) => thread.isRunning}>
				<ComposerPrimitive.Cancel asChild>
					<Button
						type="button"
						variant="default"
						size="icon"
						className="aui-composer-cancel size-8 rounded-full"
						aria-label="Stop generating"
					>
						<SquareIcon className="aui-composer-cancel-icon size-3 fill-current" />
					</Button>
				</ComposerPrimitive.Cancel>
			</AssistantIf>
		</div>
	);
};
