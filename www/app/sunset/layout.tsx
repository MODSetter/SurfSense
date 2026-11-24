import "../(home)/home.css";

/**
 * The sunset page's frame: the marketing palette and column, but no site nav or footer.
 *
 * Legacy 0.0.x desktop apps load this page in their own window. That window hands a link to
 * the user's browser only when it opens a new window (`setWindowOpenHandler`); a plain link
 * would navigate inside the old app. So the page carries no client-side navigation at all,
 * and every link on it opens a new window.
 */
export default function SunsetLayout({ children }: { children: React.ReactNode }) {
	return (
		<main className="ss-home min-h-screen">
			<div className="ss-home-page">{children}</div>
		</main>
	);
}
