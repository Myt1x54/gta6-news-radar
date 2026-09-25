"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const WEIGHT_KEYS: [string, string][] = [
  ["video_score", "AI video score"],
  ["credibility", "Source credibility"],
  ["source_count", "Source count"],
  ["reddit_engagement", "Reddit engagement"],
  ["youtube_trend", "YouTube trend match"],
  ["freshness", "Freshness"],
];

type Settings = {
  alert_threshold: number;
  email_enabled: boolean;
  weights: Record<string, number>;
};

export default function SettingsForm({ initial }: { initial: Settings }) {
  const [threshold, setThreshold] = useState<number>(initial.alert_threshold ?? 60);
  const [emailEnabled, setEmailEnabled] = useState<boolean>(initial.email_enabled ?? true);
  const [weights, setWeights] = useState<Record<string, number>>(initial.weights ?? {});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const router = useRouter();

  const sum = Object.values(weights).reduce((a, b) => a + Number(b || 0), 0);

  async function save() {
    setSaving(true);
    setSaved(false);
    const { error } = await createClient()
      .from("settings")
      .update({
        alert_threshold: Number(threshold),
        email_enabled: emailEnabled,
        weights,
        updated_at: new Date().toISOString(),
      })
      .eq("id", 1);
    setSaving(false);
    if (!error) {
      setSaved(true);
      router.refresh();
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <h2 className="mb-3 text-sm font-semibold text-zinc-300">Alerts</h2>
        <label className="mb-1 block text-xs text-zinc-400">
          Breaking-alert threshold (rank 0–100)
        </label>
        <input
          type="number"
          min={0}
          max={100}
          value={threshold}
          onChange={(e) => setThreshold(Number(e.target.value))}
          className="w-28 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
        />
        <p className="mt-1 text-xs text-zinc-500">
          Lower = more alerts. Current data tops out near ~67.
        </p>

        <label className="mt-4 flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={emailEnabled}
            onChange={(e) => setEmailEnabled(e.target.checked)}
            className="h-4 w-4"
          />
          Email enabled (alerts + daily digest)
        </label>
      </section>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-zinc-300">Ranking weights</h2>
          <span className={`text-xs ${Math.abs(sum - 1) < 0.001 ? "text-emerald-400" : "text-amber-400"}`}>
            sum: {sum.toFixed(2)}
          </span>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {WEIGHT_KEYS.map(([key, label]) => (
            <div key={key}>
              <label className="mb-1 block text-xs text-zinc-400">{label}</label>
              <input
                type="number"
                step="0.05"
                min={0}
                max={1}
                value={weights[key] ?? 0}
                onChange={(e) =>
                  setWeights({ ...weights, [key]: Number(e.target.value) })
                }
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
              />
            </div>
          ))}
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          Weights should add up to ~1.00. Changes apply on the collector&apos;s next run.
        </p>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save settings"}
        </button>
        {saved && <span className="text-xs text-emerald-400">Saved ✓</span>}
      </div>
    </div>
  );
}
