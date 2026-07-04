import Playground from "@/components/Playground";
import { InfoBanner } from "@/components/ui/InfoBanner";

export default function PlaygroundPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-8">
      <InfoBanner storageKey="playground">
        Send a real request through Arbiter. Pick an example or write your own, then watch it get classified,
        routed to a model, scored and priced - all live.
      </InfoBanner>
      <Playground />
    </div>
  );
}
