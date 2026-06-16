import { type NextRequest, NextResponse } from "next/server";
import { OAUTH_RESULT_COOKIE, type OAuthCallbackResult } from "@/contracts/types/oauth.types";

export async function GET(
	request: NextRequest,
	{ params }: { params: Promise<{ search_space_id: string }> }
) {
	const { search_space_id } = await params;
	const searchParams = request.nextUrl.searchParams;

	const payload: OAuthCallbackResult = {
		success: searchParams.get("success"),
		error: searchParams.get("error"),
		connector: searchParams.get("connector"),
		connectorId: searchParams.get("connectorId"),
	};
	const result = JSON.stringify(payload);

	const response = NextResponse.redirect(`/dashboard/${search_space_id}/new-chat`, {
		status: 302,
	});
	response.cookies.set(OAUTH_RESULT_COOKIE, result, {
		path: "/",
		maxAge: 60,
		httpOnly: false,
		sameSite: "lax",
	});

	return response;
}
