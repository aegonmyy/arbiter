import PolicyTable from "@/components/PolicyTable";
import { Baseline } from "@/components/RightRail";

export default function ModelsPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 sm:px-8">
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2"><PolicyTable /></div>
        <Baseline />
      </div>
    </div>
  );
}
