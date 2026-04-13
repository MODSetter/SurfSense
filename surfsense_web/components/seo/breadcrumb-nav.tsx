import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { BreadcrumbJsonLd } from "./json-ld";

interface BreadcrumbItem {
	name: string;
	href: string;
}

interface BreadcrumbNavProps {
	items: BreadcrumbItem[];
	className?: string;
}

export function BreadcrumbNav({ items, className }: BreadcrumbNavProps) {
	const jsonLdItems = items.map((item) => ({
		name: item.name,
		url: `https://surfsense.com${item.href}`,
	}));

	return (
		<>
			<BreadcrumbJsonLd items={jsonLdItems} />
			<nav aria-label="Breadcrumb" className={className}>
				<ol className="flex items-center gap-1.5 text-sm text-muted-foreground">
					{items.map((item, index) => {
						const isLast = index === items.length - 1;
						return (
							<li key={item.href} className="flex items-center gap-1.5">
								{index > 0 && (
									<ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
								)}
								{isLast ? (
									<span className="font-medium text-foreground" aria-current="page">
										{item.name}
									</span>
								) : (
									<Link
										href={item.href}
										className="transition-colors hover:text-foreground"
									>
										{item.name}
									</Link>
								)}
							</li>
						);
					})}
				</ol>
			</nav>
		</>
	);
}
