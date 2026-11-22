/**
 * The notice on `/terms` and `/privacy` while their November 2026 redrafts wait for review.
 *
 * Both pages were rewritten for the free app run by its maintainer as an individual, after
 * SurfSense Inc. wound down. Neither has had a lawyer's or the maintainer's read yet, so each
 * page shows this notice until its own `REVIEWED` constant is set to `true`. It is visible on
 * purpose: an unreviewed draft should not pass for a final policy.
 */
export function LegalDraftNotice({ reviewed }: { reviewed: boolean }) {
	if (reviewed) return null;
	return (
		<p
			role="note"
			className="mx-auto mb-10 max-w-3xl rounded-2xl border border-amber-300 bg-amber-100 px-5 py-4 text-sm font-medium text-amber-950"
		>
			Draft for review: this page has been rewritten for the free SurfSense app and is waiting for
			its maintainer's review. It may still change before it takes effect.
		</p>
	);
}
