import { type NextRequest, NextResponse } from "next/server";

const OAUTH_RESULT_COOKIE = "connector_oauth_result";

export async function GET(
	request: NextRequest,
	{ params }: { params: Promise<{ search_space_id: string }> }
) {
	const { search_space_id } = await params;
	const searchParams = request.nextUrl.searchParams;

	const result = JSON.stringify({
		success: searchParams.get("success"),
		error: searchParams.get("error"),
		connector: searchParams.get("connector"),
		connectorId: searchParams.get("connectorId"),
	});

	const redirectUrl = new URL(`/dashboard/${search_space_id}/new-chat`, request.url);

	const response = NextResponse.redirect(redirectUrl, { status: 302 });
	response.cookies.set(OAUTH_RESULT_COOKIE, result, {
		path: "/",
		maxAge: 60,
		httpOnly: false,
		sameSite: "lax",
	});

	return response;
}
