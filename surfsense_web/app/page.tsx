import { redirect } from "next/navigation";

/** No landing page: `/` is the sign-in page, which sends a signed-in user on to the app. */
export default function RootPage() {
	redirect("/login");
}
