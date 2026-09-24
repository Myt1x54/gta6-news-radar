"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { CATEGORIES, STATUSES } from "@/lib/types";
import { labelize } from "@/lib/ui";

const selectClass =
  "rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-200 outline-none focus:border-zinc-500";

export default function FeedControls() {
  const router = useRouter();
  const sp = useSearchParams();

  function update(key: string, value: string) {
    const p = new URLSearchParams(sp.toString());
    if (value) p.set(key, value);
    else p.delete(key);
    router.push(`/?${p.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <select
        className={selectClass}
        value={sp.get("sort") ?? "rank"}
        onChange={(e) => update("sort", e.target.value === "rank" ? "" : e.target.value)}
      >
        <option value="rank">Sort: Rank</option>
        <option value="new">Sort: Newest</option>
      </select>

      <select
        className={selectClass}
        value={sp.get("category") ?? ""}
        onChange={(e) => update("category", e.target.value)}
      >
        <option value="">All categories</option>
        {CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {labelize(c)}
          </option>
        ))}
      </select>

      <select
        className={selectClass}
        value={sp.get("status") ?? ""}
        onChange={(e) => update("status", e.target.value)}
      >
        <option value="">All statuses</option>
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>

      <select
        className={selectClass}
        value={sp.get("min") ?? ""}
        onChange={(e) => update("min", e.target.value)}
      >
        <option value="">Any score</option>
        <option value="40">Rank ≥ 40</option>
        <option value="55">Rank ≥ 55</option>
        <option value="75">Rank ≥ 75</option>
      </select>

      <select
        className={selectClass}
        value={sp.get("hours") ?? ""}
        onChange={(e) => update("hours", e.target.value)}
      >
        <option value="">Any time</option>
        <option value="24">Last 24h</option>
        <option value="48">Last 48h</option>
        <option value="168">Last 7d</option>
      </select>
    </div>
  );
}
