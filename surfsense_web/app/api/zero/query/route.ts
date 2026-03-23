import { mustGetQuery } from "@rocicorp/zero";
import { handleQueryRequest } from "@rocicorp/zero/server";
import { NextResponse } from "next/server";
import { queries } from "@/zero/queries";
import { schema } from "@/zero/schema";

export async function POST(request: Request) {
	const result = await handleQueryRequest(
		(name, args) => {
			const query = mustGetQuery(queries, name);
			return query.fn({ args, ctx: undefined });
		},
		schema,
		request,
	);

	return NextResponse.json(result);
}
