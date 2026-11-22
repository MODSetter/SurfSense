import { siteText } from "@/components/site/site-text";

/** A plugin's tools as its list names them, as the app's plugin page shows them. */
export function PluginTools({ tools }: { tools: string[] }) {
	if (!tools.length) {
		return <p className={siteText.body}>Tools aren't listed for this plugin.</p>;
	}
	return (
		<ul className="m-0 grid list-none grid-cols-1 gap-2 p-0 sm:grid-cols-2">
			{tools.map((tool) => (
				<li key={tool} className="min-w-0">
					<code className="inline-block max-w-full truncate rounded-md bg-muted px-2.5 py-1 text-sm text-muted-foreground">
						{tool}
					</code>
				</li>
			))}
		</ul>
	);
}
