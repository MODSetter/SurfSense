import { mustGetQuery } from "@rocicorp/zero";
import { handleQueryRequest } from "@rocicorp/zero/server";
import { NextResponse } from "next/server";
import type { Context } from "@/types/zero";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

const backendURL =
	process.env.FASTAPI_BACKEND_INTERNAL_URL ||
	process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL ||
	"http://localhost:8000";

async function authenticateRequest(
	request: Request
): Promise<{ ctx: Context; error?: never } | { ctx?: never; error: NextResponse }> {
	const authHeader = request.headers.get("Authorization");
	if (!authHeader?.startsWith("Bearer ")) {
		return { ctx: undefined };
	}

	try {
		const res = await fetch(`${backendURL}/users/me`, {
			headers: { Authorization: authHeader },
		});

		if (!res.ok) {
			return { error: NextResponse.json({ error: "Unauthorized" }, { status: 401 }) };
		}

		const user = await res.json();
		return { ctx: { userId: String(user.id) } };
	} catch {
		return { error: NextResponse.json({ error: "Auth service unavailable" }, { status: 503 }) };
	}
}

export async function POST(request: Request) {
	const auth = await authenticateRequest(request);
	if (auth.error) {
		return auth.error;
	}

	const result = await handleQueryRequest(
		(name, args) => {
			const query = mustGetQuery(queries, name);
			return query.fn({ args, ctx: auth.ctx });
		},
		schema,
		request
	);

	return NextResponse.json(result);
}
