"use client";

import { useCallback, useState } from "react";
import { ImageConfigDialog } from "@/components/shared/image-config-dialog";
import { ModelConfigDialog } from "@/components/shared/model-config-dialog";
import { VisionConfigDialog } from "@/components/shared/vision-config-dialog";
import type {
	GlobalImageGenConfig,
	GlobalNewLLMConfig,
	GlobalVisionLLMConfig,
	ImageGenerationConfig,
	NewLLMConfigPublic,
	VisionLLMConfig,
} from "@/contracts/types/new-llm-config.types";
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

	// Image config dialog state
	const [imageDialogOpen, setImageDialogOpen] = useState(false);
	const [selectedImageConfig, setSelectedImageConfig] = useState<
		ImageGenerationConfig | GlobalImageGenConfig | null
	>(null);
	const [isImageGlobal, setIsImageGlobal] = useState(false);
	const [imageDialogMode, setImageDialogMode] = useState<"create" | "edit" | "view">("view");

	// Vision config dialog state
	const [visionDialogOpen, setVisionDialogOpen] = useState(false);
	const [selectedVisionConfig, setSelectedVisionConfig] = useState<
		VisionLLMConfig | GlobalVisionLLMConfig | null
	>(null);
	const [isVisionGlobal, setIsVisionGlobal] = useState(false);
	const [visionDialogMode, setVisionDialogMode] = useState<"create" | "edit" | "view">("view");

	// Default provider for create dialogs
	const [defaultLLMProvider, setDefaultLLMProvider] = useState<string | undefined>();
	const [defaultImageProvider, setDefaultImageProvider] = useState<string | undefined>();
	const [defaultVisionProvider, setDefaultVisionProvider] = useState<string | undefined>();

	// LLM handlers
	const handleEditLLMConfig = useCallback(
		(config: NewLLMConfigPublic | GlobalNewLLMConfig, global: boolean) => {
			setSelectedConfig(config);
			setIsGlobal(global);
			setDialogMode(global ? "view" : "edit");
			setDefaultLLMProvider(undefined);
			setDialogOpen(true);
		},
		[]
	);

	const handleAddNewLLM = useCallback((provider?: string) => {
		setSelectedConfig(null);
		setIsGlobal(false);
		setDialogMode("create");
		setDefaultLLMProvider(provider);
		setDialogOpen(true);
	}, []);

	const handleDialogClose = useCallback((open: boolean) => {
		setDialogOpen(open);
		if (!open) setSelectedConfig(null);
	}, []);

	// Image model handlers
	const handleAddImageModel = useCallback((provider?: string) => {
		setSelectedImageConfig(null);
		setIsImageGlobal(false);
		setImageDialogMode("create");
		setDefaultImageProvider(provider);
		setImageDialogOpen(true);
	}, []);

	const handleEditImageConfig = useCallback(
		(config: ImageGenerationConfig | GlobalImageGenConfig, global: boolean) => {
			setSelectedImageConfig(config);
			setIsImageGlobal(global);
			setImageDialogMode(global ? "view" : "edit");
			setDefaultImageProvider(undefined);
			setImageDialogOpen(true);
		},
		[]
	);

	const handleImageDialogClose = useCallback((open: boolean) => {
		setImageDialogOpen(open);
		if (!open) setSelectedImageConfig(null);
	}, []);

	// Vision model handlers
	const handleAddVisionModel = useCallback((provider?: string) => {
		setSelectedVisionConfig(null);
		setIsVisionGlobal(false);
		setVisionDialogMode("create");
		setDefaultVisionProvider(provider);
		setVisionDialogOpen(true);
	}, []);

	const handleEditVisionConfig = useCallback(
		(config: VisionLLMConfig | GlobalVisionLLMConfig, global: boolean) => {
			setSelectedVisionConfig(config);
			setIsVisionGlobal(global);
			setVisionDialogMode(global ? "view" : "edit");
			setDefaultVisionProvider(undefined);
			setVisionDialogOpen(true);
		},
		[]
	);

	const handleVisionDialogClose = useCallback((open: boolean) => {
		setVisionDialogOpen(open);
		if (!open) setSelectedVisionConfig(null);
	}, []);

	return (
		<div className="flex items-center gap-2">
			<ModelSelector
				onEditLLM={handleEditLLMConfig}
				onAddNewLLM={handleAddNewLLM}
				onEditImage={handleEditImageConfig}
				onAddNewImage={handleAddImageModel}
				onEditVision={handleEditVisionConfig}
				onAddNewVision={handleAddVisionModel}
				className={className}
			/>
			<ModelConfigDialog
				open={dialogOpen}
				onOpenChange={handleDialogClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={dialogMode}
				defaultProvider={defaultLLMProvider}
			/>
			<ImageConfigDialog
				open={imageDialogOpen}
				onOpenChange={handleImageDialogClose}
				config={selectedImageConfig}
				isGlobal={isImageGlobal}
				searchSpaceId={searchSpaceId}
				mode={imageDialogMode}
				defaultProvider={defaultImageProvider}
			/>
			<VisionConfigDialog
				open={visionDialogOpen}
				onOpenChange={handleVisionDialogClose}
				config={selectedVisionConfig}
				isGlobal={isVisionGlobal}
				searchSpaceId={searchSpaceId}
				mode={visionDialogMode}
				defaultProvider={defaultVisionProvider}
			/>
		</div>
	);
}
