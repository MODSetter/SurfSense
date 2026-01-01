"use client";

import { useAtomValue } from "jotai";
import { type FC, createContext, useContext, useState, useCallback, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { activeSearchSpaceIdAtom } from "@/atoms/search-spaces/search-space-query.atoms";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { DocumentUploadTab } from "@/components/sources/DocumentUploadTab";

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

	const handleOpenChange = useCallback((open: boolean) => {
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
	}, [closeDialog]);

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
			<DialogContent className="max-w-4xl w-[95vw] sm:w-full h-[calc(100vh-2rem)] sm:h-[85vh] flex flex-col p-0 gap-0 overflow-hidden border border-border bg-muted text-foreground [&>button]:right-3 sm:[&>button]:right-12 [&>button]:top-4 sm:[&>button]:top-10 [&>button]:opacity-80 hover:[&>button]:opacity-100 [&>button]:z-[100] [&>button_svg]:size-4 sm:[&>button_svg]:size-5">
				<div className="flex-1 min-h-0 relative overflow-hidden">
					<div className="h-full overflow-y-auto">
						<div className="px-3 sm:px-12 pt-12 sm:pt-24 pb-6 sm:pb-16">
							<DocumentUploadTab searchSpaceId={searchSpaceId} onSuccess={handleSuccess} />
						</div>
					</div>
					{/* Bottom fade shadow */}
					<div className="absolute bottom-0 left-0 right-0 h-2 sm:h-7 bg-gradient-to-t from-muted via-muted/80 to-transparent pointer-events-none z-10" />
				</div>
			</DialogContent>
		</Dialog>
	);
};

