import type { ReactNode } from "react";

/**
 * Wraps the /free hub and all /free/[model_slug] subpages.
 *
 * Previously mounted <AdSenseScript /> to scope ads to this route tree. The
 * ads came off with anonymous chat: the pages now send visitors to signup
 * rather than monetising them in place.
 */
export default function FreeSectionLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
