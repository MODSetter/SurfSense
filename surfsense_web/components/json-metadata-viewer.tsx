import { FileJson } from "lucide-react";
import React from "react";
import { defaultStyles, JsonView } from "react-json-view-lite";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
	DialogTrigger,
} from "@/components/ui/dialog";
import "react-json-view-lite/dist/index.css";

interface JsonMetadataViewerProps {
	title: string;
	metadata: any;
	trigger?: React.ReactNode;
}

export function JsonMetadataViewer({ title, metadata, trigger }: JsonMetadataViewerProps) {
	// Ensure metadata is a valid object
	const jsonData = React.useMemo(() => {
		if (!metadata) return {};

		try {
			// If metadata is a string, try to parse it
			if (typeof metadata === "string") {
				return JSON.parse(metadata);
			}
			// Otherwise, use it as is
			return metadata;
		} catch (error) {
			console.error("Error parsing JSON metadata:", error);
			return { error: "Invalid JSON metadata" };
		}
	}, [metadata]);

	return (
		<Dialog>
			<DialogTrigger asChild>
				{trigger || (
					<Button variant="ghost" size="sm" className="flex items-center gap-1">
						<FileJson size={16} />
						<span>View Metadata</span>
					</Button>
				)}
			</DialogTrigger>
			<DialogContent className="max-w-4xl max-h-[80vh] overflow-y-auto">
				<DialogHeader>
					<DialogTitle>{title} - Metadata</DialogTitle>
				</DialogHeader>
				<div className="mt-4 p-4 bg-muted/30 rounded-md">
					<JsonView data={jsonData} style={defaultStyles} />
				</div>
			</DialogContent>
		</Dialog>
	);
}
