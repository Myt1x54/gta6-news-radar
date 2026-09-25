import Header from "@/components/Header";
import { createClient } from "@/lib/supabase/server";
import type { Article, YouTubeTrend } from "@/lib/types";
import { timeAgo } from "@/lib/ui";

export const dynamic = "force-dynamic";

function fmt(n: number | null): string {
  if (!n) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(Math.round(n));
}

export default async function TrendingPage() {
  const supabase = await createClient();
  const since = new Date(Date.now() - 12 * 3600_000).toISOString();

  const { data: trendsRaw } = await supabase
    .from("youtube_trends")
    .select("*")
    .gte("captured_at", since)
    .order("view_velocity", { ascending: false })
    .limit(60);

  // de-dupe by video_id (keep the highest-velocity capture)
  const seen = new Set<string>();
  const trends: YouTubeTrend[] = [];
  for (const t of (trendsRaw ?? []) as YouTubeTrend[]) {
    if (seen.has(t.video_id)) continue;
    seen.add(t.video_id);
    trends.push(t);
    if (trends.length >= 15) break;
  }

  // competitor uploads: recent items from the youtube_rss creator channels
  const { data: ytSources } = await supabase
    .from("sources")
    .select("id,name")
    .eq("type", "youtube_rss");
  const nameById = new Map<number, string>(
    (ytSources ?? []).map((s: { id: number; name: string }) => [s.id, s.name]),
  );
  let uploads: Article[] = [];
  if ((ytSources ?? []).length) {
    const { data } = await supabase
      .from("articles")
      .select("id,title,url,published_at,source_id")
      .in("source_id", Array.from(nameById.keys()))
      .order("published_at", { ascending: false })
      .limit(12);
    uploads = (data ?? []) as Article[];
  }

  const capturedAt = trends[0]?.captured_at;

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-5">
        <div className="mb-4 flex items-baseline justify-between">
          <h1 className="text-lg font-semibold">🔥 Trending on YouTube</h1>
          {capturedAt && (
            <span className="text-xs text-zinc-500">updated {timeAgo(capturedAt)}</span>
          )}
        </div>

        {trends.length === 0 ? (
          <p className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-8 text-center text-sm text-zinc-400">
            No trend data yet — the YouTube trends job runs every few hours.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {trends.map((t, i) => (
              <a
                key={t.id}
                href={`https://www.youtube.com/watch?v=${t.video_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 rounded-xl border border-zinc-800 bg-zinc-900/40 p-3 hover:border-zinc-700"
              >
                <div className="w-6 text-center text-sm font-bold text-zinc-500">
                  {i + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium text-zinc-100">
                    {t.title}
                  </div>
                  <div className="text-xs text-zinc-500">{t.channel}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-emerald-400">
                    {fmt(t.view_velocity)}/h
                  </div>
                  <div className="text-[11px] text-zinc-500">{fmt(t.views)} views</div>
                </div>
              </a>
            ))}
          </div>
        )}

        <h2 className="mb-3 mt-8 text-sm font-semibold text-zinc-300">
          🎬 Latest from tracked creators
        </h2>
        {uploads.length === 0 ? (
          <p className="text-sm text-zinc-500">No recent creator uploads.</p>
        ) : (
          <ul className="space-y-2">
            {uploads.map((u) => (
              <li key={u.id} className="text-sm">
                <a
                  href={u.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-200 hover:text-emerald-300"
                >
                  {u.title || u.url}
                </a>
                <div className="text-xs text-zinc-500">
                  {u.source_id ? nameById.get(u.source_id) ?? "creator" : "creator"}
                  {u.published_at ? ` · ${timeAgo(u.published_at)}` : ""}
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
    </>
  );
}
