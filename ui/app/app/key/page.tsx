import ApiKeyCenter from "@/components/ApiKeyCenter";
import { InfoBanner } from "@/components/ui/InfoBanner";

export default function KeyPage() {
  return (
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-8">
      <InfoBanner storageKey="key">
        This is your API key control center. Copy it into your OpenAI client, watch your usage against the rate
        limits, and pause or revoke it any time.
      </InfoBanner>
      <ApiKeyCenter />
    </div>
  );
}
