"use client";

import { useCallback, useState } from "react";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { ImageConfigSidebar } from "./image-config-sidebar";
import { ImageModelSelector } from "./image-model-selector";
import { ModelConfigSidebar } from "./model-config-sidebar";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
}

export function ChatHeader({ searchSpaceId }: ChatHeaderProps) {
	// LLM config sidebar state
	const [sidebarOpen, setSidebarOpen] = useState(false);
	const [selectedConfig, setSelectedConfig] = useState<
		NewLLMConfigPublic | GlobalNewLLMConfig | null
	>(null);
	const [isGlobal, setIsGlobal] = useState(false);
	const [sidebarMode, setSidebarMode] = useState<"create" | "edit" | "view">("view");

	// Image config sidebar state
	const [imageSidebarOpen, setImageSidebarOpen] = useState(false);
	const [selectedImageConfig, setSelectedImageConfig] = useState<
		ImageGenerationConfig | GlobalImageGenConfig | null
	>(null);
	const [isImageGlobal, setIsImageGlobal] = useState(false);
	const [imageSidebarMode, setImageSidebarMode] = useState<"create" | "edit" | "view">("view");

	// LLM handlers
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
		if (!open) setSelectedConfig(null);
	}, []);

	// Image model handlers
	const handleAddImageModel = useCallback(() => {
		setSelectedImageConfig(null);
		setIsImageGlobal(false);
		setImageSidebarMode("create");
		setImageSidebarOpen(true);
	}, []);

	const handleEditImageConfig = useCallback(
		(config: ImageGenerationConfig | GlobalImageGenConfig, global: boolean) => {
			setSelectedImageConfig(config);
			setIsImageGlobal(global);
			setImageSidebarMode(global ? "view" : "edit");
			setImageSidebarOpen(true);
		},
		[]
	);

	const handleImageSidebarClose = useCallback((open: boolean) => {
		setImageSidebarOpen(open);
		if (!open) setSelectedImageConfig(null);
	}, []);

	return (
		<div className="flex items-center gap-2">
			<ModelSelector onEdit={handleEditConfig} onAddNew={handleAddNew} />
			<ImageModelSelector onEdit={handleEditImageConfig} onAddNew={handleAddImageModel} />
			<ModelConfigSidebar
				open={sidebarOpen}
				onOpenChange={handleSidebarClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={sidebarMode}
			/>
			<ImageConfigSidebar
				open={imageSidebarOpen}
				onOpenChange={handleImageSidebarClose}
				config={selectedImageConfig}
				isGlobal={isImageGlobal}
				searchSpaceId={searchSpaceId}
				mode={imageSidebarMode}
			/>
		</div>
	);
}
