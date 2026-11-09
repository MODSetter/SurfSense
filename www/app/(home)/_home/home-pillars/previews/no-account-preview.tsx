// What a hosted notebook turns on for you; here every one stays off.
const SETTINGS = ["Require sign-in", "Cloud sync", "Share usage data"];

/** Account settings with every switch off, like the private row's network switch. */
export function NoAccountPreview() {
	return (
		<div
			aria-hidden="true"
			className="flex w-full max-w-56 flex-col divide-y divide-border rounded-xl bg-card px-4 py-1 shadow-sm ring-1 ring-black/5"
		>
			{SETTINGS.map((setting) => (
				<div key={setting} className="flex items-center justify-between gap-3 py-2.5">
					<span className="text-xs text-foreground">{setting}</span>
					<span className="flex h-4 w-7 shrink-0 items-center rounded-full bg-muted-foreground/25 p-0.5">
						<span className="size-3 rounded-full bg-white shadow-xs" />
					</span>
				</div>
			))}
		</div>
	);
}
