import type { Metadata } from "next";
import { ContactFormGridWithDetails } from "@/components/contact/contact-form";

export const metadata: Metadata = {
	title: "Contact | SurfSense",
	description: "Get in touch with the SurfSense team.",
};

const page = () => {
	return (
		<div>
			<ContactFormGridWithDetails />
		</div>
	);
};

export default page;
