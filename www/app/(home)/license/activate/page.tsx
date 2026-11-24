import type { Metadata } from "next";
import { NoLicenseNeeded } from "../no-license-needed";

/** The old activation guide; every licence email sent before the wind-down links here. */

export const metadata: Metadata = {
	title: "SurfSense needs no licence",
	description:
		"SurfSense is free. From version 2.4.0 every feature works with no licence file to activate.",
	robots: { index: false, follow: true },
};

export default function LicenseActivatePage() {
	return <NoLicenseNeeded heading="Nothing to activate" />;
}
