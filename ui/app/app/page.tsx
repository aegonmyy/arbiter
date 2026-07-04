import StatsBar from "@/components/StatsBar";
import MiniStats from "@/components/MiniStats";
import IntegrationCard from "@/components/IntegrationCard";
import RoutingFeed from "@/components/RoutingFeed";
import { HowItWorks, PriceAlerts } from "@/components/RightRail";
import { InfoBanner } from "@/components/ui/InfoBanner";

export default function OverviewPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-8">
      <InfoBanner storageKey="overview">
        Arbiter is a drop-in OpenAI-compatible endpoint. It routes each request to the cheapest model that still
        gets it right on the BTL runtime, checks the answer, and learns - so you stop paying premium prices for
        simple work. Try it in the Playground.
      </InfoBanner>
      <StatsBar />
      <MiniStats />
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="space-y-5 lg:col-span-2">
          <RoutingFeed />
        </div>
        <div className="space-y-5">
          <HowItWorks />
          <PriceAlerts />
          <IntegrationCard />
        </div>
      </div>
    </div>
  );
}
