import { Instrument_Sans } from "next/font/google";

// Text font for the marketing routes and the docs; the app routes stay on Roboto.
// One loader call, so both trees share a single @font-face.
// Taking over --font-sans keeps `font-sans` utilities on it too.
export const siteSansFont = Instrument_Sans({
	subsets: ["latin"],
	display: "optional",
	variable: "--font-sans",
});
