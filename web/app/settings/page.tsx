import Header from "@/components/Header";
import SettingsForm from "@/components/SettingsForm";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const DEFAULTS = {
  alert_threshold: 60,
  email_enabled: true,
  weights: {
    video_score: 0.35,
    credibility: 0.15,
    source_count: 0.15,
    reddit_engagement: 0.1,
    youtube_trend: 0.1,
    freshness: 0.15,
  },
};

export default async function SettingsPage() {
  const supabase = await createClient();
  const { data } = await supabase.from("settings").select("*").eq("id", 1).single();

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-5">
        <h1 className="mb-4 text-lg font-semibold">⚙️ Settings</h1>
        <SettingsForm initial={{ ...DEFAULTS, ...(data ?? {}) }} />
      </main>
    </>
  );
}
