"use client";

import { useAtomValue } from "jotai";
import { AlertTriangle, Settings, Upload } from "lucide-react";
import Link from "next/link";
import {
	createContext,
	type FC,
	type ReactNode,
	useCallback,
	useContext,
	useRef,
	useState,
} from "react";
import {
	globalNewLLMConfigsAtom,
	llmPreferencesAtom,
} from "@/atoms/new-llm-config/new-llm-config-query.atoms";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { DocumentUploadTab } from "@/components/sources/DocumentUploadTab";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

// Context for opening the dialog from anywhere
interface DocumentUploadDialogContextType {
	openDialog: () => void;
	closeDialog: () => void;
}

const DocumentUploadDialogContext = createContext<DocumentUploadDialogContextType | null>(null);

export const useDocumentUploadDialog = () => {
	const context = useContext(DocumentUploadDialogContext);
	if (!context) {
		throw new Error("useDocumentUploadDialog must be used within DocumentUploadDialogProvider");
	}
	return context;
};

// Provider component
export const DocumentUploadDialogProvider: FC<{ children: ReactNode }> = ({ children }) => {
	const [isOpen, setIsOpen] = useState(false);
	const isClosingRef = useRef(false);

	const openDialog = useCallback(() => {
		// Prevent opening if we just closed (debounce)
		if (isClosingRef.current) {
			return;
		}
		setIsOpen(true);
	}, []);

	const closeDialog = useCallback(() => {
		isClosingRef.current = true;
		setIsOpen(false);
		// Reset the flag after a short delay to allow for file picker to close
		setTimeout(() => {
			isClosingRef.current = false;
		}, 300);
	}, []);

	const handleOpenChange = useCallback(
		(open: boolean) => {
			if (!open) {
				// Only close if not already in closing state
				if (!isClosingRef.current) {
					closeDialog();
				}
			} else {
				// Only open if not in the middle of closing
				if (!isClosingRef.current) {
					setIsOpen(true);
				}
			}
		},
		[closeDialog]
	);

	return (
		<DocumentUploadDialogContext.Provider value={{ openDialog, closeDialog }}>
			{children}
			<DocumentUploadPopupContent isOpen={isOpen} onOpenChange={handleOpenChange} />
		</DocumentUploadDialogContext.Provider>
	);
};

// Internal component that renders the dialog
const DocumentUploadPopupContent: FC<{
	isOpen: boolean;
	onOpenChange: (open: boolean) => void;
}> = ({ isOpen, onOpenChange }) => {
	const searchSpaceId = useAtomValue(activeSearchSpaceIdAtom);
	const { data: preferences = {}, isFetching: preferencesLoading } =
		useAtomValue(llmPreferencesAtom);
	const { data: globalConfigs = [], isFetching: globalConfigsLoading } =
		useAtomValue(globalNewLLMConfigsAtom);

	if (!searchSpaceId) return null;

	const handleSuccess = () => {
		onOpenChange(false);
	};

	// Check if document summary LLM is properly configured
	// - If ID is 0 (Auto mode), we need global configs to be available
	// - If ID is positive (user config) or negative (specific global config), it's configured
	// - If ID is null/undefined, it's not configured
	const docSummaryLlmId = preferences.document_summary_llm_id;
	const isAutoMode = docSummaryLlmId === 0;
	const hasGlobalConfigs = globalConfigs.length > 0;

	const hasDocumentSummaryLLM =
		docSummaryLlmId !== null &&
		docSummaryLlmId !== undefined &&
		// If it's Auto mode, we need global configs to actually be available
		(!isAutoMode || hasGlobalConfigs);

	const isLoading = preferencesLoading || globalConfigsLoading;

	return (
		<Dialog open={isOpen} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-4xl w-[95vw] sm:w-full h-[calc(100dvh-2rem)] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground [&>button]:right-3 sm:[&>button]:right-12 [&>button]:top-3 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button]:z-[100] [&>button_svg]:size-4 sm:[&>button_svg]:size-5">
				<DialogTitle className="sr-only">Upload Document</DialogTitle>

				{/* Scrollable container for mobile */}
				<div className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
					{/* Header - scrolls with content on mobile */}
					<div className="sticky top-0 z-20 bg-muted px-4 sm:px-12 pt-4 sm:pt-10 pb-2 sm:pb-0">
						{/* Upload header */}
						<div className="flex items-center gap-2 sm:gap-4 mb-2 sm:mb-6">
							<div className="flex h-9 w-9 sm:h-14 sm:w-14 items-center justify-center rounded-lg sm:rounded-xl bg-primary/10 border border-primary/20 flex-shrink-0">
								<Upload className="size-4 sm:size-7 text-primary" />
							</div>
							<div className="flex-1 min-w-0 pr-8 sm:pr-0">
								<h2 className="text-base sm:text-2xl font-semibold tracking-tight">
									Upload Documents
								</h2>
								<p className="text-xs sm:text-base text-muted-foreground mt-0.5 sm:mt-1 line-clamp-1 sm:line-clamp-none">
									Upload and sync your documents to your search space
								</p>
							</div>
						</div>
					</div>

					{/* Content */}
					<div className="px-4 sm:px-12 pb-4 sm:pb-16">
						{!isLoading && !hasDocumentSummaryLLM ? (
							<Alert variant="destructive" className="mb-4">
								<AlertTriangle className="h-4 w-4" />
								<AlertTitle>LLM Configuration Required</AlertTitle>
								<AlertDescription className="mt-2">
									<p className="mb-3">
										{isAutoMode && !hasGlobalConfigs
											? "Auto mode is selected but no global LLM configurations are available. Please configure a custom LLM in Settings to process and summarize your uploaded documents."
											: "You need to configure a Document Summary LLM before uploading files. This LLM is used to process and summarize your uploaded documents."}
									</p>
									<Button asChild size="sm" variant="outline">
										<Link href={`/dashboard/${searchSpaceId}/settings`}>
											<Settings className="mr-2 h-4 w-4" />
											Go to Settings
										</Link>
									</Button>
								</AlertDescription>
							</Alert>
						) : (
							<DocumentUploadTab searchSpaceId={searchSpaceId} onSuccess={handleSuccess} />
						)}
					</div>
				</div>

				{/* Bottom fade shadow - hidden on very small screens */}
				<div className="hidden sm:block absolute bottom-0 left-0 right-0 h-7 bg-gradient-to-t from-muted via-muted/80 to-transparent pointer-events-none z-10" />
			</DialogContent>
		</Dialog>
	);
};
