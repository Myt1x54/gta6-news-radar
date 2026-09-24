"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { STATUSES, type Status } from "@/lib/types";
import { statusStyle } from "@/lib/ui";

export default function StatusControl({
  storyId,
  status,
}: {
  storyId: string;
  status: Status;
}) {
  const [current, setCurrent] = useState<Status>(status);
  const [saving, setSaving] = useState(false);
  const router = useRouter();

  async function set(s: Status) {
    if (s === current) return;
    setSaving(true);
    const { error } = await createClient()
      .from("stories")
      .update({ status: s, last_updated_at: new Date().toISOString() })
      .eq("id", storyId);
    setSaving(false);
    if (!error) {
      setCurrent(s);
      router.refresh();
    }
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {STATUSES.map((s) => (
        <button
          key={s}
          disabled={saving}
          onClick={() => set(s)}
          className={`rounded-full border px-2.5 py-1 text-xs capitalize transition disabled:opacity-50 ${
            current === s
              ? statusStyle[s]
              : "border-zinc-700 text-zinc-500 hover:text-zinc-300"
          }`}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
