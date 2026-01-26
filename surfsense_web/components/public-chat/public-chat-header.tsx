import { formatDistanceToNow } from "date-fns";
import Image from "next/image";
import Link from "next/link";

interface PublicChatHeaderProps {
	title: string;
	createdAt: string;
}

export function PublicChatHeader({ title, createdAt }: PublicChatHeaderProps) {
	const timeAgo = formatDistanceToNow(new Date(createdAt), { addSuffix: true });

	return (
		<header className="sticky top-0 z-10 -mx-4 mb-4 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
			<div className="mx-auto flex max-w-(--thread-max-width) items-center justify-between py-3">
				<div className="flex items-center gap-3">
					<Link href="/" className="shrink-0">
						<Image
							src="/surfsenselogo.png"
							alt="SurfSense"
							width={32}
							height={32}
							className="rounded"
						/>
					</Link>
					<div className="min-w-0">
						<h1 className="truncate font-medium">{title}</h1>
						<p className="text-xs text-muted-foreground">{timeAgo}</p>
					</div>
				</div>
			</div>
		</header>
	);
}
