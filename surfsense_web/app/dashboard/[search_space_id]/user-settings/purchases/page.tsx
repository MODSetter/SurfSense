import { AutoReloadSettings } from "../components/AutoReloadSettings";
import { PurchaseHistoryContent } from "../components/PurchaseHistoryContent";

export default function Page() {
	return (
		<div className="space-y-6">
			<AutoReloadSettings />
			<PurchaseHistoryContent />
		</div>
	);
}
