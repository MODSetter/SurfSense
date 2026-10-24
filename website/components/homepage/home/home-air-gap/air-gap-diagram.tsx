import { AirGapDiorama } from "@/components/homepage/home/home-air-gap/diorama/air-gap-diorama";
import { ON_YOUR_MACHINE } from "@/components/homepage/home/home-content";
import { siteText } from "@/components/site/site-text";
import { cn } from "@/lib/utils";

/**
 * "Runs entirely on your machine" as an isometric diorama beside its three
 * claims. The current claim (set by `AirGapScrollSteps`) lights its objects
 * and the others dim.
 */
export function AirGapDiagram({ className }: { className?: string }) {
	return (
		<div className={cn("grid items-center gap-6 lg:grid-cols-[1.15fr_1fr] lg:gap-16", className)}>
			<AirGapDiorama />
			<ol className="flex flex-col">
				{ON_YOUR_MACHINE.map((claim, index) => (
					<li
						key={claim.title}
						data-claim={claim.node}
						className="ss-airgap-claim border-t border-border py-6 first:border-t-0 lg:first:pt-0"
					>
						<div className="flex items-baseline gap-3">
							<span className="ss-airgap-step grid size-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold tabular-nums">
								{index + 1}
							</span>
							<div>
								<p className={siteText.h3}>{claim.title}</p>
								<p className={cn(siteText.body, "mt-1.5 text-sm")}>{claim.body}</p>
							</div>
						</div>
					</li>
				))}
			</ol>
		</div>
	);
}
