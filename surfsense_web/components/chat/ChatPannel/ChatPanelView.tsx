"use client";

import { Pencil, Podcast } from "lucide-react";
import { useContext } from "react";
import { cn } from "@/lib/utils";
import { chatInterfaceContext } from "../ChatInterface";
import { ConfigModal } from "./ConfigModal";

interface ChatPanelViewProps {
	chat_id: string;
}

export function ChatPanelView({ chat_id: chatId }: ChatPanelViewProps) {
	const context = useContext(chatInterfaceContext);
	if (!context) {
		throw new Error("chatInterfaceContext must be used within a ChatProvider");
	}

	const { isChatPannelOpen, setIsChatPannelOpen } = context;

	return (
		<div className="w-full">
			<div
				className={cn(
					"w-full h-full p-4 border-b",
					!isChatPannelOpen && "flex items-center justify-center"
				)}
			>
				{isChatPannelOpen ? (
					<div className=" space-y-3 rounded-xl p-3 bg-gradient-to-r from-slate-400/50 to-slate-200/50 dark:from-slate-400/30 dark:to-slate-800/60">
						<div className="w-full flex items-center justify-between">
							<Podcast strokeWidth={1} />
							<ConfigModal />
						</div>
						<p>Generate Podcast</p>
					</div>
				) : (
					<button
						title="Generate Podcast"
						type="button"
						onClick={() => setIsChatPannelOpen(!isChatPannelOpen)}
					>
						<Podcast strokeWidth={1} />
					</button>
				)}
			</div>
		</div>
	);
}
