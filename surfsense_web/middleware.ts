// Middleware temporarily disabled for client-side i18n implementation
// Server-side i18n routing would require restructuring entire app directory to app/[locale]/...
// which is too invasive for this project

import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

// Empty middleware - just pass through all requests
export function middleware(request: NextRequest) {
	return NextResponse.next();
}
