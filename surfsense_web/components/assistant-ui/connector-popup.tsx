import { useAtomValue } from "jotai";
import {
	ChevronRightIcon,
	Loader2,
	Plug2,
	Plus,
} from "lucide-react";
import Link from "next/link";
import {
	type FC,
	useCallback,
	useRef,
	useState,
} from "react";
import { getDocumentTypeLabel } from "@/app/dashboard/[search_space_id]/documents/(manage)/components/DocumentTypeIcon";
import { documentTypeCountsAtom } from "@/atoms/documents/document-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { useSearchSourceConnectors } from "@/hooks/use-search-source-connectors";
import { cn } from "@/lib/utils";

export const ConnectorIndicator: FC = () => {
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

	// Get document types that have documents in the search space
	const activeDocumentTypes = documentTypeCounts
		? Object.entries(documentTypeCounts).filter(([_, count]) => count > 0)
		: [];

	const hasConnectors = connectors.length > 0;
	const hasSources = hasConnectors || activeDocumentTypes.length > 0;
	const totalSourceCount = connectors.length + activeDocumentTypes.length;

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
						hasSources ? `View ${totalSourceCount} connected sources` : "Add your first connector"
					}
					onMouseEnter={handleMouseEnter}
					onMouseLeave={handleMouseLeave}
				>
					{isLoading ? (
						<Loader2 className="size-4 animate-spin" />
					) : (
						<>
							<Plug2 className="size-4" />
							{totalSourceCount > 0 && (
								<span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-medium rounded-full bg-primary text-primary-foreground shadow-sm">
									{totalSourceCount > 99 ? "99+" : totalSourceCount}
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
						<div className="flex items-center justify-between">
							<p className="text-xs font-medium text-muted-foreground">Connected Sources</p>
							<span className="text-xs font-medium bg-muted px-1.5 py-0.5 rounded">
								{totalSourceCount}
							</span>
						</div>
						<div className="flex flex-wrap gap-2">
							{/* Document types from the search space */}
							{activeDocumentTypes.map(([docType]) => (
								<div
									key={docType}
									className="flex items-center gap-1.5 rounded-md bg-muted/80 px-2.5 py-1.5 text-xs border border-border/50"
								>
									{getConnectorIcon(docType, "size-3.5")}
									<span className="truncate max-w-[100px]">{getDocumentTypeLabel(docType)}</span>
								</div>
							))}
							{/* Search source connectors */}
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
						<div className="pt-1 border-t border-border/50">
							<Link
								href={`/dashboard/${searchSpaceId}/connectors/add`}
								className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
							>
								<Plus className="size-3" />
								Add more sources
								<ChevronRightIcon className="size-3" />
							</Link>
						</div>
					</div>
				) : (
					<div className="space-y-2">
						<p className="text-sm font-medium">No sources yet</p>
						<p className="text-xs text-muted-foreground">
							Add documents or connect data sources to enhance search results.
						</p>
						<Link
							href={`/dashboard/${searchSpaceId}/connectors/add`}
							className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors mt-1"
						>
							<Plus className="size-3" />
							Add Connector
						</Link>
					</div>
				)}
			</PopoverContent>
		</Popover>
	);
};

