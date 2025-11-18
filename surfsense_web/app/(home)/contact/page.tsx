import React from "react";
import { ContactFormGridWithDetails } from "@/components/contact/contact-form";
import { RouteGuard } from "@/components/RouteGuard";

const page = () => {
	return (
		<RouteGuard routeKey="contact">
			<div>
				<ContactFormGridWithDetails />
			</div>
		</RouteGuard>
	);
};

export default page;
