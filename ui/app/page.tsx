import Header from "@/components/Header";
import Hero from "@/components/Hero";
import StatsBar from "@/components/StatsBar";
import MiniStats from "@/components/MiniStats";
import SavingsChart from "@/components/SavingsChart";
import RoutingFeed from "@/components/RoutingFeed";
import PolicyTable from "@/components/PolicyTable";
import RightRail from "@/components/RightRail";

export default function Home() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-[82rem] space-y-5 px-4 py-6 sm:px-6">
        <Hero />
        <StatsBar />
        <MiniStats />
        <div className="grid gap-5 lg:grid-cols-3">
          <div className="flex flex-col gap-5 lg:col-span-2">
            <SavingsChart />
            <RoutingFeed />
            <PolicyTable />
          </div>
          <RightRail />
        </div>
      </main>
    </>
  );
}
