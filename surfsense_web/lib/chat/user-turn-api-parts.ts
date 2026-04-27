import type { AppendMessage } from "@assistant-ui/react";

const MAX_IMAGES = 4;

export type NewChatUserImagePayload = {
	media_type: "image/png" | "image/jpeg" | "image/webp";
	data: string;
};

function dataUrlToPayload(dataUrl: string): NewChatUserImagePayload | null {
	const m = /^data:(image\/(?:png|jpeg|webp|jpg));base64,([\s\S]+)$/i.exec(dataUrl.trim());
	if (!m) return null;
	let media = m[1].toLowerCase() as string;
	if (media === "image/jpg") media = "image/jpeg";
	if (media !== "image/png" && media !== "image/jpeg" && media !== "image/webp") return null;
	const data = m[2].replace(/\s/g, "");
	if (!data) return null;
	return { media_type: media as NewChatUserImagePayload["media_type"], data };
}

function collectImageDataUrlsFromParts(parts: AppendMessage["content"]): string[] {
	const out: string[] = [];
	for (const part of parts) {
		if (typeof part !== "object" || part === null || !("type" in part)) continue;
		if (part.type !== "image") continue;
		const img = "image" in part && typeof part.image === "string" ? part.image : null;
		if (img && dataUrlToPayload(img)) out.push(img);
	}
	return out;
}

export function extractUserTurnForNewChatApi(
	message: AppendMessage,
	extraDataUrls: readonly string[]
): { userQuery: string; userImages: NewChatUserImagePayload[] } {
	let userQuery = "";
	for (const part of message.content) {
		if (part.type === "text") {
			userQuery += part.text;
		}
	}

	const merged = [...extraDataUrls, ...collectImageDataUrlsFromParts(message.content)];
	const payloads: NewChatUserImagePayload[] = [];
	const seen = new Set<string>();
	for (const url of merged) {
		const p = dataUrlToPayload(url);
		if (!p) continue;
		if (seen.has(p.data)) continue;
		seen.add(p.data);
		payloads.push(p);
		if (payloads.length >= MAX_IMAGES) break;
	}

	return { userQuery, userImages: payloads };
}
