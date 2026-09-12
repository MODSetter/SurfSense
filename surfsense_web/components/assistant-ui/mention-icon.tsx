import { Folder, MessageSquare, Plug } from "lucide-react";
import { getConnectorIcon } from "@/contracts/enums/connectorIcons";
import { ArtifactFormatIcon } from "@/features/artifacts/ui/artifact-format-icon";

interface MentionIconData {
	kind?: "doc" | "folder" | "connector" | "thread";
	document_type?: string;
	connector_type?: string;
}

export function MentionIcon({
	mention,
	artifactFormat,
	className,
}: {
	mention: MentionIconData;
	artifactFormat?: string;
	className?: string;
}) {
	const iconClassName = className ?? "size-4";
	if (mention.kind === "folder") return <Folder className={iconClassName} />;
	if (mention.kind === "thread") return <MessageSquare className={iconClassName} />;
	if (mention.kind === "connector") {
		return (
			getConnectorIcon(
				mention.connector_type ?? mention.document_type ?? "UNKNOWN",
				iconClassName
			) ?? <Plug className={iconClassName} />
		);
	}
	if (mention.document_type === "ARTIFACT") {
		return <ArtifactFormatIcon format={artifactFormat} className={iconClassName} />;
	}
	return getConnectorIcon(mention.document_type ?? "UNKNOWN", iconClassName);
}
