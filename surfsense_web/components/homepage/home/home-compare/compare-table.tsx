import { VerdictMark } from "@/components/homepage/home/home-compare/verdict-mark";
import { COMPARE_PRODUCTS, COMPARE_ROWS } from "@/components/homepage/home/home-content";
import { cn } from "@/lib/utils";

const LAST_ROW = COMPARE_ROWS.length - 1;

/**
 * The full matrix in a card, with the SurfSense column raised as a white
 * column of its own, the way a pricing table marks its recommended plan.
 *
 * A real `<table>`, because the brief wants a comparison an AI Overview can
 * lift. `border-separate` rather than `collapse`, so the raised column's cells
 * can take its rounded ends.
 */
export function CompareTable() {
	return (
		<div className="rounded-2xl border border-border bg-card px-4 py-5 shadow-xs md:px-8 md:py-6">
			<table className="w-full border-separate border-spacing-0 text-sm">
				<caption className="sr-only">
					SurfSense compared with NotebookLM, AnythingLLM and Open Notebook
				</caption>
				<thead>
					<tr>
						<th scope="col" className="w-40 lg:w-48">
							<span className="sr-only">Capability</span>
						</th>
						{COMPARE_PRODUCTS.map((product) =>
							product.key === "ours" ? (
								<th
									key={product.key}
									scope="col"
									className="rounded-t-xl border-x border-t border-border bg-white px-5 pt-5 pb-4 text-left font-semibold text-foreground"
								>
									{product.name}
								</th>
							) : (
								<th
									key={product.key}
									scope="col"
									className="px-5 pt-5 pb-4 text-left font-medium text-muted-foreground"
								>
									{product.name}
								</th>
							)
						)}
					</tr>
				</thead>
				<tbody>
					{COMPARE_ROWS.map((row, index) => {
						const last = index === LAST_ROW;
						return (
							<tr key={row.label}>
								<th
									scope="row"
									className={cn(
										"py-4 pr-4 text-left font-normal text-muted-foreground",
										!last && "border-b border-border"
									)}
								>
									{row.label}
								</th>
								{COMPARE_PRODUCTS.map((product) => {
									const cell = row[product.key];
									const ours = product.key === "ours";
									return (
										<td
											key={product.key}
											className={cn(
												"px-5 py-4 align-middle",
												ours
													? "border-x border-border bg-white font-semibold text-foreground"
													: "text-foreground/80",
												ours && last && "rounded-b-xl border-b pb-5",
												!last && "border-b border-border"
											)}
										>
											<span className="flex items-center gap-2.5">
												<VerdictMark verdict={cell.verdict} />
												{cell.text}
											</span>
										</td>
									);
								})}
							</tr>
						);
					})}
				</tbody>
			</table>
		</div>
	);
}
