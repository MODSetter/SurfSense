"use client";

import { DocumentRightPanel } from "./DocumentRightPanel";

interface MobileDocumentsWorkspaceViewProps {
	onOpenChange?: (open: boolean) => void;
}

/**
 * Page-style Documents destination used by the mobile workspace shell.
 * DocumentRightPanel keeps the browser state and behavior shared with desktop;
 * workspaceView swaps only the surrounding navigation and heading structure.
 */
export function MobileDocumentsWorkspaceView({
	onOpenChange = () => {},
}: MobileDocumentsWorkspaceViewProps) {
	return <DocumentRightPanel open onOpenChange={onOpenChange} embedded workspaceView />;
}
