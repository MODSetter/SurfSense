import { MemoryRouter } from "react-router-dom";
import { Toaster } from "@/routes/ui/toaster";
import { Routing } from "~routes";

function IndexPopup() {
	return (
		<MemoryRouter>
			<Routing />
			<Toaster />
		</MemoryRouter>
	);
}

export default IndexPopup;
