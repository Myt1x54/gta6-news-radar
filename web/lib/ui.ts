import type { Category, Status } from "./types";

export function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

// Tailwind color classes per category badge.
export const categoryStyle: Record<Category, string> = {
  official: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  leak: "bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30",
  rumor: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  trailer_media: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  price_date: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  gameplay_detail: "bg-cyan-500/15 text-cyan-300 border-cyan-500/30",
  community_drama: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  other: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
};

export const statusStyle: Record<Status, string> = {
  new: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
  shortlisted: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  pitched: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  used: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  rejected: "bg-rose-500/15 text-rose-300 border-rose-500/30",
};

export function labelize(s: string | null | undefined): string {
  if (!s) return "";
  return s.replace(/_/g, " ");
}

// 0-100 rank -> tailwind text color
export function rankColor(score: number): string {
  if (score >= 75) return "text-emerald-400";
  if (score >= 55) return "text-amber-400";
  return "text-zinc-400";
}
