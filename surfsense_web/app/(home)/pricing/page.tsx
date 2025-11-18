import React from "react";
import PricingBasic from "@/components/pricing/pricing-section";
import { RouteGuard } from "@/components/RouteGuard";

const page = () => {
	return (
		<RouteGuard routeKey="pricing">
			<div>
				<PricingBasic />
			</div>
		</RouteGuard>
	);
};

export default page;
