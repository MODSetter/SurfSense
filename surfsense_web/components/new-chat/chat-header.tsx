"use client";

import { useCallback, useState } from "react";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
} from "@/contracts/types/new-llm-config.types";
import { ImageConfigSidebar } from "./image-config-sidebar";
import { ModelConfigDialog } from "./model-config-dialog";
import { ModelSelector } from "./model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
	className?: string;
}

export function ChatHeader({ searchSpaceId, className }: ChatHeaderProps) {
	// LLM config dialog state
	const [dialogOpen, setDialogOpen] = useState(false);
	const [selectedConfig, setSelectedConfig] = useState<
		NewLLMConfigPublic | GlobalNewLLMConfig | null
	>(null);
	const [isGlobal, setIsGlobal] = useState(false);
	const [dialogMode, setDialogMode] = useState<"create" | "edit" | "view">("view");

	// Image config sidebar state
	const [imageSidebarOpen, setImageSidebarOpen] = useState(false);
	const [selectedImageConfig, setSelectedImageConfig] = useState<
		ImageGenerationConfig | GlobalImageGenConfig | null
	>(null);
	const [isImageGlobal, setIsImageGlobal] = useState(false);
	const [imageSidebarMode, setImageSidebarMode] = useState<"create" | "edit" | "view">("view");

	// LLM handlers
	const handleEditLLMConfig = useCallback(
		(config: NewLLMConfigPublic | GlobalNewLLMConfig, global: boolean) => {
			setSelectedConfig(config);
			setIsGlobal(global);
			setDialogMode(global ? "view" : "edit");
			setDialogOpen(true);
		},
		[]
	);

	const handleAddNewLLM = useCallback(() => {
		setSelectedConfig(null);
		setIsGlobal(false);
		setDialogMode("create");
		setDialogOpen(true);
	}, []);

	const handleDialogClose = useCallback((open: boolean) => {
		setDialogOpen(open);
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
			<ModelSelector
				onEditLLM={handleEditLLMConfig}
				onAddNewLLM={handleAddNewLLM}
				onEditImage={handleEditImageConfig}
				onAddNewImage={handleAddImageModel}
				className={className}
			/>
			<ModelConfigDialog
				open={dialogOpen}
				onOpenChange={handleDialogClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={dialogMode}
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
