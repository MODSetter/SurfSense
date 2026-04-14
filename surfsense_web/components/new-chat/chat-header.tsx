"use client";

import { useCallback, useEffect, useState } from "react";
import { useSetAtom } from "jotai";
import { selectedSystemModelIdAtom } from "@/atoms/new-llm-config/system-models-query.atoms";
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
import { isCloud } from "@/lib/env-config";
import { ModelSelector } from "./model-selector";
import { SystemModelSelector } from "./system-model-selector";

interface ChatHeaderProps {
	searchSpaceId: number;
	className?: string;
}

export function ChatHeader({ searchSpaceId, className }: ChatHeaderProps) {
	// Reset system model selection when search space changes
	const setSelectedSystemModelId = useSetAtom(selectedSystemModelIdAtom);
	useEffect(() => {
		setSelectedSystemModelId(null);
	}, [searchSpaceId, setSelectedSystemModelId]);

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
		setImageDialogMode("create");
		setImageDialogOpen(true);
	}, []);

	const handleEditImageConfig = useCallback(
		(config: ImageGenerationConfig | GlobalImageGenConfig, global: boolean) => {
			setSelectedImageConfig(config);
			setIsImageGlobal(global);
			setImageDialogMode(global ? "view" : "edit");
			setImageDialogOpen(true);
		},
		[]
	);

	const handleImageDialogClose = useCallback((open: boolean) => {
		setImageDialogOpen(open);
		if (!open) setSelectedImageConfig(null);
	}, []);

	// Vision model handlers
	const handleAddVisionModel = useCallback(() => {
		setSelectedVisionConfig(null);
		setIsVisionGlobal(false);
		setVisionDialogMode("create");
		setVisionDialogOpen(true);
	}, []);

	const handleEditVisionConfig = useCallback(
		(config: VisionLLMConfig | GlobalVisionLLMConfig, global: boolean) => {
			setSelectedVisionConfig(config);
			setIsVisionGlobal(global);
			setVisionDialogMode(global ? "view" : "edit");
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
			{isCloud() ? (
				<SystemModelSelector className={className} />
			) : (
				<ModelSelector
					onEditLLM={handleEditLLMConfig}
					onAddNewLLM={handleAddNewLLM}
					onEditImage={handleEditImageConfig}
					onAddNewImage={handleAddImageModel}
					onEditVision={handleEditVisionConfig}
					onAddNewVision={handleAddVisionModel}
					className={className}
				/>
			)}
			<ModelConfigDialog
				open={dialogOpen}
				onOpenChange={handleDialogClose}
				config={selectedConfig}
				isGlobal={isGlobal}
				searchSpaceId={searchSpaceId}
				mode={dialogMode}
			/>
			<ImageConfigDialog
				open={imageDialogOpen}
				onOpenChange={handleImageDialogClose}
				config={selectedImageConfig}
				isGlobal={isImageGlobal}
				searchSpaceId={searchSpaceId}
				mode={imageDialogMode}
			/>
			<VisionConfigDialog
				open={visionDialogOpen}
				onOpenChange={handleVisionDialogClose}
				config={selectedVisionConfig}
				isGlobal={isVisionGlobal}
				searchSpaceId={searchSpaceId}
				mode={visionDialogMode}
			/>
		</div>
	);
}
