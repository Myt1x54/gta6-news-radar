"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function GenerateIdeasButton({ storyId }: { storyId: string }) {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const router = useRouter();

  async function generate() {
    setLoading(true);
    setMsg(null);
    try {
      const res = await fetch("/api/generate-ideas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ storyId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "failed");
      setMsg(`Added ${data.inserted} ✓`);
      router.refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-3 flex items-center gap-3">
      <button
        onClick={generate}
        disabled={loading}
        className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-500 disabled:opacity-50"
      >
        {loading ? "Generating…" : "✨ Generate more ideas"}
      </button>
      {msg && <span className="text-xs text-zinc-400">{msg}</span>}
    </div>
  );
}
