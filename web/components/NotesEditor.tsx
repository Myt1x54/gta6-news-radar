"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";

export default function NotesEditor({
  storyId,
  initial,
}: {
  storyId: string;
  initial: string | null;
}) {
  const [notes, setNotes] = useState(initial ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save() {
    setSaving(true);
    setSaved(false);
    const { error } = await createClient()
      .from("stories")
      .update({ notes })
      .eq("id", storyId);
    setSaving(false);
    if (!error) setSaved(true);
  }

  return (
    <div>
      <textarea
        value={notes}
        onChange={(e) => {
          setNotes(e.target.value);
          setSaved(false);
        }}
        rows={4}
        placeholder="Your notes…"
        className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm outline-none focus:border-zinc-500"
      />
      <div className="mt-2 flex items-center gap-3">
        <button
          onClick={save}
          disabled={saving}
          className="rounded-lg bg-zinc-800 px-3 py-1.5 text-xs hover:bg-zinc-700 disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save notes"}
        </button>
        {saved && <span className="text-xs text-emerald-400">Saved ✓</span>}
      </div>
    </div>
  );
}
