"use client";

import { useSetAtom } from "jotai";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { documentsSidebarOpenAtom } from "@/atoms/documents/ui.atoms";
import { rightPanelCollapsedAtom } from "@/atoms/layout/right-panel.atom";
import { MobileDocumentsWorkspaceView } from "@/components/layout/ui/right-panel/MobileDocumentsWorkspaceView";
import { useIsMobile } from "@/hooks/use-mobile";
import { getWorkspaceIdNumber } from "@/lib/route-params";

export default function DocumentsPage() {
	const params = useParams();
	const router = useRouter();
	const isMobile = useIsMobile();
	const [isHydrated, setIsHydrated] = useState(false);
	const setDocumentsOpen = useSetAtom(documentsSidebarOpenAtom);
	const setRightPanelCollapsed = useSetAtom(rightPanelCollapsedAtom);
	const workspaceId = getWorkspaceIdNumber(params);

	useEffect(() => setIsHydrated(true), []);

	useEffect(() => {
		if (!isHydrated || isMobile || workspaceId === undefined) return;

		setDocumentsOpen(true);
		setRightPanelCollapsed(false);
		router.replace(`/dashboard/${workspaceId}/new-chat`);
	}, [isHydrated, isMobile, router, setDocumentsOpen, setRightPanelCollapsed, workspaceId]);

	if (!isHydrated || !isMobile || workspaceId === undefined) return null;

	return <MobileDocumentsWorkspaceView />;
}
