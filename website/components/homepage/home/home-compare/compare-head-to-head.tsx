import { VerdictMark } from "@/components/homepage/home/home-compare/verdict-mark";
import {
	COMPARE_PRODUCTS,
	COMPARE_ROWS,
	type CompareCell,
} from "@/components/homepage/home/home-content";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const RIVALS = COMPARE_PRODUCTS.filter((product) => product.key !== "ours");

function Cell({ cell, ours }: { cell: CompareCell; ours: boolean }) {
	return (
		<span
			className={
				ours
					? "flex items-start gap-2 font-semibold text-foreground"
					: "flex items-start gap-2 text-foreground/80"
			}
		>
			<VerdictMark verdict={cell.verdict} />
			{cell.text}
		</span>
	);
}

/**
 * The phone layout: SurfSense against one product at a time, so nothing
 * scrolls sideways. The full table stays in the markup for search; this is
 * what a narrow screen shows instead of it.
 */
export function CompareHeadToHead() {
	return (
		<Tabs defaultValue={RIVALS[0].key}>
			<TabsList className="flex h-auto w-full rounded-full bg-(--home-badge) p-1">
				{RIVALS.map((rival) => (
					<TabsTrigger
						key={rival.key}
						value={rival.key}
						className="flex-1 rounded-full px-2 py-2 text-xs font-medium text-muted-foreground data-[state=active]:bg-card data-[state=active]:text-foreground"
					>
						{rival.name}
					</TabsTrigger>
				))}
			</TabsList>

			{RIVALS.map((rival) => (
				<TabsContent
					key={rival.key}
					value={rival.key}
					className="mt-4 overflow-hidden rounded-2xl border border-border bg-card shadow-xs"
				>
					<div className="grid grid-cols-2 border-b border-border text-sm">
						<p className="bg-white px-4 py-3 font-semibold text-foreground">SurfSense</p>
						<p className="px-4 py-3 font-medium text-muted-foreground">{rival.name}</p>
					</div>
					<dl className="m-0">
						{COMPARE_ROWS.map((row) => (
							<div key={row.label} className="border-b border-border last:border-b-0">
								<dt className="px-4 pt-3 text-xs text-muted-foreground">{row.label}</dt>
								<dd className="m-0 grid grid-cols-2 gap-4 px-4 pt-1.5 pb-3 text-sm">
									<Cell cell={row.ours} ours />
									<Cell cell={row[rival.key]} ours={false} />
								</dd>
							</div>
						))}
					</dl>
				</TabsContent>
			))}
		</Tabs>
	);
}
