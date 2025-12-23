"use client";

import { useCallback, useState } from "react";
import type {
	GlobalNewLLMConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { ModelConfigSidebar } from "./model-config-sidebar";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
}

export function ChatHeader({ searchSpaceId }: ChatHeaderProps) {
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
			// Reset state when closing
			setSelectedConfig(null);
		}
	}, []);

	return (
		<>
			{/* Header Bar */}
			<div className="flex items-center justify-between px-4 py-2 border-b border-border/30 bg-background/80 backdrop-blur-sm">
				<ModelSelector onEdit={handleEditConfig} onAddNew={handleAddNew} />
			</div>

			{/* Config Sidebar */}
			<ModelConfigSidebar
				open={sidebarOpen}
				onOpenChange={handleSidebarClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={sidebarMode}
			/>
		</>
	);
}
