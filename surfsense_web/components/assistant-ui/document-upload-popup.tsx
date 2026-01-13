"use client";

import { useAtomValue } from "jotai";
import { Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import {
	createContext,
	type FC,
	type ReactNode,
	useCallback,
	useContext,
	useRef,
	useState,
} from "react";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { DocumentUploadTab } from "@/components/sources/DocumentUploadTab";
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
	const router = useRouter();

	if (!searchSpaceId) return null;

	const handleSuccess = () => {
		onOpenChange(false);
		router.push(`/dashboard/${searchSpaceId}/documents`);
	};

	return (
		<Dialog open={isOpen} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-4xl w-[95vw] sm:w-full max-h-[calc(100vh-2rem)] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground [&>button]:right-3 sm:[&>button]:right-12 [&>button]:top-4 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button]:z-[100] [&>button_svg]:size-4 sm:[&>button_svg]:size-5">
				<DialogTitle className="sr-only">Upload Document</DialogTitle>

				{/* Fixed Header */}
				<div className="flex-shrink-0 px-4 sm:px-12 pt-6 sm:pt-10 transition-shadow duration-200 relative z-10">
					{/* Upload header */}
					<div className="flex items-center gap-2 sm:gap-4 mb-2 sm:mb-6">
						<div className="flex h-10 w-10 sm:h-14 sm:w-14 items-center justify-center rounded-lg sm:rounded-xl bg-primary/10 border border-primary/20 flex-shrink-0">
							<Upload className="size-5 sm:size-7 text-primary" />
						</div>
						<div className="flex-1 min-w-0">
							<h2 className="text-lg sm:text-2xl font-semibold tracking-tight">Upload Documents</h2>
							<p className="text-xs sm:text-base text-muted-foreground mt-0.5 sm:mt-1">
								Upload and sync your documents to your search space
							</p>
						</div>
					</div>
				</div>

				{/* Scrollable Content */}
				<div className="flex-1 min-h-0 relative overflow-hidden">
					<div className="h-full overflow-y-auto">
						<div className="px-6 sm:px-12 pb-5 sm:pb-16">
							<DocumentUploadTab
								searchSpaceId={searchSpaceId}
								onSuccess={handleSuccess}
							/>
						</div>
					</div>
					{/* Bottom fade shadow */}
					<div className="absolute bottom-0 left-0 right-0 h-2 sm:h-7 bg-gradient-to-t from-muted via-muted/80 to-transparent pointer-events-none z-10" />
				</div>
			</DialogContent>
		</Dialog>
	);
};
