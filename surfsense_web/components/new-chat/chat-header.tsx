"use client";

import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import type {
	GlobalNewLLMConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { ImageModelSelector } from "./image-model-selector";
import { ModelConfigSidebar } from "./model-config-sidebar";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
}

export function ChatHeader({ searchSpaceId }: ChatHeaderProps) {
	const router = useRouter();
	const [sidebarOpen, setSidebarOpen] = useState(false);
	const [selectedConfig, setSelectedConfig] = useState<
		NewLLMConfigPublic | GlobalNewLLMConfig | null
	>(null);
	const [isGlobal, setIsGlobal] = useState(false);
	const [sidebarMode, setSidebarMode] = useState<"create" | "edit" | "view">("view");

	const handleEditConfig = useCallback(
		(config: NewLLMConfigPublic | GlobalNewLLMConfig, global: boolean) => {
			setSelectedConfig(config);
			setIsGlobal(global);
			setSidebarMode(global ? "view" : "edit");
			setSidebarOpen(true);
		},
		[]
	);

	const handleAddNew = useCallback(() => {
		setSelectedConfig(null);
		setIsGlobal(false);
		setSidebarMode("create");
		setSidebarOpen(true);
	}, []);

	const handleSidebarClose = useCallback((open: boolean) => {
		setSidebarOpen(open);
		if (!open) {
			setSelectedConfig(null);
		}
	}, []);

	const handleAddImageModel = useCallback(() => {
		// Navigate to settings image-models tab
		router.push(`/dashboard/${searchSpaceId}/settings?tab=image-models`);
	}, [router, searchSpaceId]);

	return (
		<div className="flex items-center gap-2">
			<ModelSelector onEdit={handleEditConfig} onAddNew={handleAddNew} />
			<ImageModelSelector onAddNew={handleAddImageModel} />
			<ModelConfigSidebar
				open={sidebarOpen}
				onOpenChange={handleSidebarClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={sidebarMode}
			/>
		</div>
	);
}
