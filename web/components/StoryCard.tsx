"use client";

import Link from "next/link";
import { useState } from "react";
import type { Story, VideoIdea } from "@/lib/types";
import { categoryStyle, labelize, rankColor, statusStyle } from "@/lib/ui";
import StatusControl from "./StatusControl";
import TimeAgo from "./TimeAgo";

function Badge({
  children,
  className,
}: {
  children: React.ReactNode;
  className: string;
}) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[11px] capitalize ${className}`}
    >
      {children}
    </span>
  );
}

export default function StoryCard({
  story,
  ideas,
}: {
  story: Story;
  ideas: VideoIdea[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 transition-colors hover:border-zinc-700">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {story.category && (
            <Badge className={categoryStyle[story.category]}>
              {labelize(story.category)}
            </Badge>
          )}
          <Badge className={statusStyle[story.status]}>{story.status}</Badge>
          <span className="text-xs text-zinc-500">
            {story.source_count} src · <TimeAgo iso={story.first_seen_at} />
          </span>
        </div>
        <div className={`text-right ${rankColor(story.rank_score)}`}>
          <div className="text-lg font-bold leading-none">
            {Math.round(story.rank_score)}
          </div>
          <div className="text-[10px] uppercase tracking-wide text-zinc-500">
            rank
          </div>
        </div>
      </div>

      <Link
        href={`/story/${story.id}`}
        className="mt-2 block text-base font-semibold leading-snug hover:text-emerald-300"
      >
        {story.headline}
      </Link>
      {story.summary && (
        <p className="mt-1 text-sm text-zinc-400">{story.summary}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500">
        <span>
          🎬 video{" "}
          <b className="text-zinc-300">{story.video_score ?? "–"}</b>/10
        </span>
        <span>
          🎯 cred{" "}
          <b className="text-zinc-300">
            {story.credibility != null
              ? Math.round(story.credibility * 100) + "%"
              : "–"}
          </b>
        </span>
        {ideas.length > 0 && (
          <button
            onClick={() => setOpen(!open)}
            className="text-emerald-400 hover:text-emerald-300"
          >
            {open
              ? "Hide ideas"
              : `${ideas.length} video idea${ideas.length > 1 ? "s" : ""}`}
          </button>
        )}
      </div>

      {open && ideas.length > 0 && (
        <ul className="mt-3 space-y-2 border-t border-zinc-800 pt-3">
          {ideas.map((i) => (
            <li key={i.id} className="text-sm">
              <div className="font-medium text-zinc-200">🎥 {i.title}</div>
              {i.hook && (
                <div className="mt-0.5 text-xs text-zinc-500">Hook: {i.hook}</div>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 border-t border-zinc-800 pt-3">
        <StatusControl storyId={story.id} status={story.status} />
      </div>
    </div>
  );
}
