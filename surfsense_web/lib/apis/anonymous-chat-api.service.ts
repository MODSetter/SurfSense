import {
	type AnonChatRequest,
	type AnonModel,
	type AnonQuotaResponse,
	anonChatRequest,
	anonQuotaResponse,
	getAnonModelResponse,
	getAnonModelsResponse,
} from "@/contracts/types/anonymous-chat.types";
import { BACKEND_URL } from "../env-config";
import { ValidationError } from "../error";

const BASE = "/api/v1/public/anon-chat";

export type AnonUploadResult =
	| { ok: true; data: { filename: string; size_bytes: number } }
	| { ok: false; reason: "quota_exceeded" };

class AnonymousChatApiService {
	private baseUrl: string;

	constructor(baseUrl: string) {
		this.baseUrl = baseUrl;
	}

	private fullUrl(path: string): string {
		return `${this.baseUrl}${BASE}${path}`;
	}

	getModels = async (): Promise<AnonModel[]> => {
		const res = await fetch(this.fullUrl("/models"), { credentials: "include" });
		if (!res.ok) throw new Error(`Failed to fetch models: ${res.status}`);
		const data = await res.json();
		const parsed = getAnonModelsResponse.safeParse(data);
		if (!parsed.success) console.error("Invalid anon models response:", parsed.error);
		return data;
	};

	getModel = async (slug: string): Promise<AnonModel> => {
		const res = await fetch(this.fullUrl(`/models/${encodeURIComponent(slug)}`), {
			credentials: "include",
		});
		if (!res.ok) {
			if (res.status === 404) throw new Error("Model not found");
			throw new Error(`Failed to fetch model: ${res.status}`);
		}
		const data = await res.json();
		const parsed = getAnonModelResponse.safeParse(data);
		if (!parsed.success) console.error("Invalid anon model response:", parsed.error);
		return data;
	};

	getQuota = async (): Promise<AnonQuotaResponse> => {
		const res = await fetch(this.fullUrl("/quota"), { credentials: "include" });
		if (!res.ok) throw new Error(`Failed to fetch quota: ${res.status}`);
		const data = await res.json();
		const parsed = anonQuotaResponse.safeParse(data);
		if (!parsed.success) console.error("Invalid anon quota response:", parsed.error);
		return data;
	};

	streamChat = async (request: AnonChatRequest): Promise<Response> => {
		const validated = anonChatRequest.safeParse(request);
		if (!validated.success) {
			throw new ValidationError(
				`Invalid request: ${validated.error.issues.map((i) => i.message).join(", ")}`
			);
		}

		return fetch(this.fullUrl("/stream"), {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			credentials: "include",
			body: JSON.stringify(validated.data),
		});
	};

	uploadDocument = async (file: File): Promise<AnonUploadResult> => {
		const formData = new FormData();
		formData.append("file", file);
		const res = await fetch(this.fullUrl("/upload"), {
			method: "POST",
			credentials: "include",
			body: formData,
		});
		if (res.status === 409) {
			return { ok: false, reason: "quota_exceeded" };
		}
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body.detail || `Upload failed: ${res.status}`);
		}
		const data = await res.json();
		return { ok: true, data };
	};

	getDocument = async (): Promise<{ filename: string; size_bytes: number } | null> => {
		const res = await fetch(this.fullUrl("/document"), { credentials: "include" });
		if (res.status === 404) return null;
		if (!res.ok) throw new Error(`Failed to fetch document: ${res.status}`);
		return res.json();
	};
}

export const anonymousChatApiService = new AnonymousChatApiService(BACKEND_URL);
