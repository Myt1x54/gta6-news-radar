import Header from "@/components/Header";
import FeedControls from "@/components/FeedControls";
import StoryCard from "@/components/StoryCard";
import { createClient } from "@/lib/supabase/server";
import type { Story, VideoIdea } from "@/lib/types";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{
  sort?: string;
  category?: string;
  status?: string;
  min?: string;
  hours?: string;
}>;

export default async function FeedPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const supabase = await createClient();

  let query = supabase.from("stories").select("*");
  if (sp.category) query = query.eq("category", sp.category);
  if (sp.status) query = query.eq("status", sp.status);
  if (sp.min) query = query.gte("rank_score", Number(sp.min));
  if (sp.hours) {
    const since = new Date(Date.now() - Number(sp.hours) * 3600_000).toISOString();
    query = query.gte("first_seen_at", since);
  }
  query =
    sp.sort === "new"
      ? query.order("first_seen_at", { ascending: false })
      : query.order("rank_score", { ascending: false });

  const { data: stories, error } = await query.limit(100);
  const list = (stories ?? []) as Story[];

  // fetch video ideas for the visible stories in one query, group by story
  const ideasByStory = new Map<string, VideoIdea[]>();
  if (list.length) {
    const { data: ideas } = await supabase
      .from("video_ideas")
      .select("*")
      .in(
        "story_id",
        list.map((s) => s.id),
      );
    for (const idea of (ideas ?? []) as VideoIdea[]) {
      const arr = ideasByStory.get(idea.story_id) ?? [];
      arr.push(idea);
      ideasByStory.set(idea.story_id, arr);
    }
  }

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-5">
        <div className="mb-4 flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <h1 className="text-lg font-semibold">Feed</h1>
            <span className="text-xs text-zinc-500">{list.length} stories</span>
          </div>
          <FeedControls />
        </div>

        {error && (
          <p className="rounded-lg bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
            Failed to load stories: {error.message}
          </p>
        )}

        {!error && list.length === 0 && (
          <p className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-8 text-center text-sm text-zinc-400">
            No stories match these filters yet.
          </p>
        )}

        <div className="flex flex-col gap-3">
          {list.map((story) => (
            <StoryCard
              key={story.id}
              story={story}
              ideas={ideasByStory.get(story.id) ?? []}
            />
          ))}
        </div>
      </main>
    </>
  );
}
