import { FileQuestion } from "lucide-react";

// Not an error: the artifact saved fine and the panel header still offers download.
export function UnviewableArtifact({ message }: { message: string }) {
	return (
		<div className="flex h-full flex-col items-center justify-center gap-3 px-5 py-4 text-center">
			<FileQuestion className="size-8 text-muted-foreground" />
			<p className="max-w-xs text-sm text-muted-foreground">{message}</p>
		</div>
	);
}
