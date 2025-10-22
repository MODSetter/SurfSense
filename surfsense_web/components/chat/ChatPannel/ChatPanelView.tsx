import { Pencil, Podcast } from "lucide-react";

export default function ChatPanelView() {
	return (
		<div className="w-full">
			<div className="w-full h-full p-4 border-b">
				<div className=" space-y-3 rounded-xl p-3 bg-gradient-to-r dark:from-slate-400/30 dark:to-slate-800/60">
					<div className="w-full flex items-center justify-between">
						<Podcast strokeWidth={1} />
						<button
							type="button"
							className="rounded-full p-2 bg-slate-400/30 hover:bg-slate-400/40"
						>
							<Pencil strokeWidth={1} className="h-4 w-4" />
						</button>
					</div>
					<p> Generate Podcast</p>
				</div>
			</div>
		</div>
	);
}
