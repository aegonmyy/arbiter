import RoutingFeed from "@/components/RoutingFeed";
import { PriceAlerts } from "@/components/RightRail";

export default function ActivityPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2"><RoutingFeed /></div>
        <PriceAlerts />
      </div>
    </div>
  );
}
