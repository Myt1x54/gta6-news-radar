import Link from "next/link";
import { notFound } from "next/navigation";
import Header from "@/components/Header";
import StatusControl from "@/components/StatusControl";
import NotesEditor from "@/components/NotesEditor";
import { createClient } from "@/lib/supabase/server";
import type { Article, Story, VideoIdea } from "@/lib/types";
import { categoryStyle, labelize, rankColor, statusStyle, timeAgo } from "@/lib/ui";

export const dynamic = "force-dynamic";

export default async function StoryPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: story } = await supabase
    .from("stories")
    .select("*")
    .eq("id", id)
    .single();
  if (!story) notFound();
  const s = story as Story;

  const [{ data: ideasData }, { data: articlesData }, { data: sourcesData }] =
    await Promise.all([
      supabase.from("video_ideas").select("*").eq("story_id", id),
      supabase
        .from("articles")
        .select("*")
        .eq("story_id", id)
        .order("published_at", { ascending: false }),
      supabase.from("sources").select("id,name"),
    ]);

  const ideas = (ideasData ?? []) as VideoIdea[];
  const articles = (articlesData ?? []) as Article[];
  const sourceName = new Map<number, string>(
    (sourcesData ?? []).map((x: { id: number; name: string }) => [x.id, x.name]),
  );

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-5">
        <Link href="/" className="text-xs text-zinc-500 hover:text-zinc-300">
          ← Back to feed
        </Link>

        <div className="mt-3 flex items-start justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {s.category && (
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] capitalize ${categoryStyle[s.category]}`}
              >
                {labelize(s.category)}
              </span>
            )}
            <span
              className={`rounded-full border px-2 py-0.5 text-[11px] capitalize ${statusStyle[s.status]}`}
            >
              {s.status}
            </span>
            <span className="text-xs text-zinc-500">
              {s.source_count} sources · first seen {timeAgo(s.first_seen_at)}
            </span>
          </div>
          <div className={`text-right ${rankColor(s.rank_score)}`}>
            <div className="text-2xl font-bold leading-none">
              {Math.round(s.rank_score)}
            </div>
            <div className="text-[10px] uppercase tracking-wide text-zinc-500">
              rank
            </div>
          </div>
        </div>

        <h1 className="mt-3 text-xl font-semibold leading-snug">{s.headline}</h1>
        {s.summary && <p className="mt-2 text-sm text-zinc-300">{s.summary}</p>}

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Stat label="Video score" value={`${s.video_score ?? "–"}/10`} />
          <Stat
            label="Credibility"
            value={s.credibility != null ? `${Math.round(s.credibility * 100)}%` : "–"}
          />
          <Stat label="Sources" value={String(s.source_count)} />
        </div>

        {(s.video_score_reason || s.credibility_reason) && (
          <div className="mt-3 space-y-1 text-xs text-zinc-500">
            {s.video_score_reason && <p>🎬 {s.video_score_reason}</p>}
            {s.credibility_reason && <p>🎯 {s.credibility_reason}</p>}
          </div>
        )}

        {/* Status */}
        <Section title="Status">
          <StatusControl storyId={s.id} status={s.status} />
        </Section>

        {/* Video ideas */}
        <Section title={`Video ideas (${ideas.length})`}>
          {ideas.length === 0 ? (
            <p className="text-sm text-zinc-500">
              Not enriched yet — the collector fills these in on its next runs.
            </p>
          ) : (
            <ul className="space-y-3">
              {ideas.map((i) => (
                <li
                  key={i.id}
                  className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3"
                >
                  <div className="flex items-center gap-2">
                    {i.format && (
                      <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400">
                        {labelize(i.format)}
                      </span>
                    )}
                    <span className="font-medium text-zinc-100">{i.title}</span>
                  </div>
                  {i.hook && (
                    <p className="mt-1 text-xs text-zinc-400">Hook: {i.hook}</p>
                  )}
                  {i.angle && (
                    <p className="mt-0.5 text-xs text-zinc-500">Angle: {i.angle}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>

        {/* Sources */}
        <Section title={`Sources (${articles.length})`}>
          <ul className="space-y-2">
            {articles.map((a) => (
              <li key={a.id} className="text-sm">
                <a
                  href={a.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-zinc-200 hover:text-emerald-300"
                >
                  {a.title || a.url}
                </a>
                <div className="text-xs text-zinc-500">
                  {a.source_id ? sourceName.get(a.source_id) ?? "source" : "source"}
                  {a.published_at ? ` · ${timeAgo(a.published_at)}` : ""}
                  {a.reddit_score != null
                    ? ` · ▲${a.reddit_score} 💬${a.reddit_comments ?? 0}`
                    : ""}
                </div>
              </li>
            ))}
          </ul>
        </Section>

        {/* Notes */}
        <Section title="Notes">
          <NotesEditor storyId={s.id} initial={s.notes} />
        </Section>

        {s.ai_model_used && (
          <p className="mt-6 text-center text-[11px] text-zinc-600">
            enriched by {s.ai_model_used}
          </p>
        )}
      </main>
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2">
      <div className="text-base font-semibold text-zinc-100">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-6">
      <h2 className="mb-2 text-sm font-semibold text-zinc-300">{title}</h2>
      {children}
    </section>
  );
}
