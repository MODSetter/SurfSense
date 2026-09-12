"use client";

import { ZoomInIcon, ZoomOutIcon } from "lucide-react";
import Image from "next/image";
import { createPortal } from "react-dom";
import { TransformComponent, TransformWrapper } from "react-zoom-pan-pinch";
import { Button } from "@/components/ui/button";
import { buildBackendUrl } from "@/lib/env-config";
import type { FileViewerProps } from "./model";

export default function ImageFileViewer({ primary, zoomControlsContainer }: FileViewerProps) {
	return (
		<div className="relative h-full overflow-hidden bg-muted/30">
			<TransformWrapper
				initialScale={1}
				minScale={0.5}
				maxScale={3}
				centerOnInit
				centerZoomedOut
				limitToBounds
				wheel={{ step: 0.1, activationKeys: ["Control"] }}
				pinch={{ step: 5 }}
				trackPadPanning={{ disabled: false }}
			>
				{({ zoomIn, zoomOut }) => (
					<>
						{zoomControlsContainer
							? createPortal(
									<div
										role="toolbar"
										className="flex items-center gap-1"
										aria-label="Image zoom controls"
									>
										<Button
											type="button"
											variant="ghost"
											size="icon"
											className="size-6 shrink-0 rounded-full text-muted-foreground"
											aria-label="Zoom out"
											onClick={() => zoomOut(0.25)}
										>
											<ZoomOutIcon className="size-4" />
										</Button>
										<Button
											type="button"
											variant="ghost"
											size="icon"
											className="size-6 shrink-0 rounded-full text-muted-foreground"
											aria-label="Zoom in"
											onClick={() => zoomIn(0.25)}
										>
											<ZoomInIcon className="size-4" />
										</Button>
									</div>,
									zoomControlsContainer
								)
							: null}
						<TransformComponent
							wrapperStyle={{ width: "100%", height: "100%" }}
							contentStyle={{
								width: "100%",
								height: "100%",
								display: "flex",
								alignItems: "center",
								justifyContent: "center",
							}}
						>
							<Image
								src={buildBackendUrl(primary.content_url)}
								alt={primary.filename}
								width={1600}
								height={1200}
								unoptimized
								className="h-auto max-h-full w-auto max-w-full rounded-md shadow-sm"
							/>
						</TransformComponent>
					</>
				)}
			</TransformWrapper>
		</div>
	);
}
