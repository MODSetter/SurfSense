import type { Metadata } from "next";
import { NoLicenseNeeded } from "../no-license-needed";

/** Stripe's old return page after a purchase; checkout is gone, so nothing lands here new. */

export const metadata: Metadata = {
	title: "SurfSense needs no licence",
	robots: { index: false, follow: true },
};

export default function LicenseSuccessPage() {
	return <NoLicenseNeeded heading="SurfSense needs no licence" />;
}
