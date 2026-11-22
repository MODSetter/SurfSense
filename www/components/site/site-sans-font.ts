import { Instrument_Sans } from "next/font/google";

// The site's one text font, set on <body> in the root layout, so every page,
// the 404 and error pages included, loads the same @font-face.
// Taking over --font-sans keeps `font-sans` utilities on it too.
export const siteSansFont = Instrument_Sans({
	subsets: ["latin"],
	display: "optional",
	variable: "--font-sans",
});
