import { baseApiService } from "./base-api.service";

export interface VideoInput {
	scenes: Record<string, unknown>[];
}

export async function generateVideoScript(
	searchSpaceId: number,
	topic: string,
	sourceContent: string,
	signal?: AbortSignal,
): Promise<VideoInput> {
	return baseApiService.post<VideoInput>(
		`/api/v1/video/generate-script?search_space_id=${searchSpaceId}`,
		undefined,
		{
			body: { topic, source_content: sourceContent },
			signal,
		},
	);
}

export interface RenderResponse {
	renderId: string;
	bucketName: string;
}

export type ProgressResponse =
	| { type: "error"; message: string }
	| { type: "progress"; progress: number }
	| { type: "done"; url: string; size: number };

async function videoApiRequest<T>(endpoint: string, body: unknown): Promise<T> {
	const res = await fetch(endpoint, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	const json = await res.json();
	if (json.type === "error") {
		throw new Error(json.message);
	}
	return json.data;
}

export async function renderVideo(inputProps: VideoInput): Promise<RenderResponse> {
	return videoApiRequest<RenderResponse>("/api/video/render", { inputProps });
}

export async function getRenderProgress(renderId: string, bucketName: string): Promise<ProgressResponse> {
	return videoApiRequest<ProgressResponse>("/api/video/progress", {
		id: renderId,
		bucketName,
	});
}
