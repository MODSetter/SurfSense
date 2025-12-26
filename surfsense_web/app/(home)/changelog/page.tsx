import { loader } from "fumadocs-core/source";
import { changelog } from "@/.source/server";
import { formatDate } from "@/lib/utils";
import { getMDXComponents } from "@/mdx-components";

const source = loader({
	baseUrl: "/changelog",
	source: changelog.toFumadocsSource(),
});

interface ChangelogData {
	title: string;
	date: string;
	version?: string;
	tags?: string[];
	body: React.ComponentType<{ components?: Record<string, React.ComponentType> }>;
}

interface ChangelogPageItem {
	url: string;
	data: ChangelogData;
}

export default async function ChangelogPage() {
	const allPages = source.getPages() as ChangelogPageItem[];
	const sortedChangelogs = allPages.sort((a, b) => {
		const dateA = new Date(a.data.date).getTime();
		const dateB = new Date(b.data.date).getTime();
		return dateB - dateA;
	});

	return (
		<div className="min-h-screen relative pt-20">
			{/* Header */}
			<div className="border-b border-border/50">
				<div className="max-w-5xl mx-auto relative">
					<div className="p-6 flex items-center justify-between">
						<div>
							<h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-gray-900 to-gray-600 dark:from-white dark:to-gray-400 bg-clip-text text-transparent">
								Changelog
							</h1>
							<p className="text-muted-foreground mt-2">
								Stay up to date with the latest updates and improvements to SurfSense.
							</p>
						</div>
					</div>
				</div>
			</div>

			{/* Timeline */}
			<div className="max-w-5xl mx-auto px-6 lg:px-10 pt-10 pb-20">
				<div className="relative">
					{sortedChangelogs.map((changelog) => {
						const MDX = changelog.data.body;
						const date = new Date(changelog.data.date);
						const formattedDate = formatDate(date);

						return (
							<div key={changelog.url} className="relative">
								<div className="flex flex-col md:flex-row gap-y-6">
									<div className="md:w-48 flex-shrink-0">
										<div className="md:sticky md:top-24 pb-10">
											<time className="text-sm font-medium text-muted-foreground block mb-3">
												{formattedDate}
											</time>

											{changelog.data.version && (
												<div className="inline-flex relative z-10 items-center justify-center w-12 h-12 text-foreground border border-border rounded-xl text-sm font-bold bg-card shadow-sm">
													{changelog.data.version}
												</div>
											)}
										</div>
									</div>

									{/* Right side - Content */}
									<div className="flex-1 md:pl-8 relative pb-10">
										{/* Vertical timeline line */}
										<div className="hidden md:block absolute top-2 left-0 w-px h-full bg-border">
											{/* Timeline dot */}
											<div className="hidden md:block absolute -translate-x-1/2 size-3 bg-primary rounded-full z-10" />
										</div>

										<div className="space-y-6">
											<div className="relative z-10 flex flex-col gap-2">
												<h2 className="text-2xl font-semibold tracking-tight text-balance">
													{changelog.data.title}
												</h2>

												{/* Tags */}
												{changelog.data.tags && changelog.data.tags.length > 0 && (
													<div className="flex flex-wrap gap-2">
														{changelog.data.tags.map((tag: string) => (
															<span
																key={tag}
																className="h-6 w-fit px-2.5 text-xs font-medium bg-muted text-muted-foreground rounded-full border flex items-center justify-center"
															>
																{tag}
															</span>
														))}
													</div>
												)}
											</div>
											<div className="prose dark:prose-invert max-w-none prose-headings:scroll-mt-8 prose-headings:font-semibold prose-a:no-underline prose-headings:tracking-tight prose-headings:text-balance prose-p:tracking-tight prose-p:text-balance prose-img:rounded-xl prose-img:shadow-lg">
												<MDX components={getMDXComponents()} />
											</div>
										</div>
									</div>
								</div>
							</div>
						);
					})}
				</div>
			</div>
		</div>
	);
}
