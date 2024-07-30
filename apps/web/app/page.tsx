import { CardsStats } from "./placeholder-stats";
import SearchUsers from "@/components/search-users";

export default async function Page() {
  return (
    <div className="flex flex-col gap-4">
      <CardsStats />
      <SearchUsers />
    </div>
  );
}
