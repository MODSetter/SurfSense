import type { Metadata } from "next";
import { NoLicenseNeeded } from "./no-license-needed";

/** The old "get your licence again" page; the app's error texts still link here. */

export const metadata: Metadata = {
	title: "SurfSense needs no licence",
	description: "SurfSense is free. From version 2.4.0 every feature works with no licence file.",
	robots: { index: false, follow: true },
};

export default function LicensePage() {
	return <NoLicenseNeeded heading="SurfSense needs no licence" />;
}
