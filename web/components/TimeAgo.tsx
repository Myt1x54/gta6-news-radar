"use client";

import { useEffect, useState } from "react";
import { timeAgo } from "@/lib/ui";

// Relative time depends on "now", which differs between the server render and
// client hydration. Render it only after mount to avoid hydration mismatches.
export default function TimeAgo({ iso }: { iso: string | null }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    setText(timeAgo(iso));
  }, [iso]);
  return <span suppressHydrationWarning>{text ?? "…"}</span>;
}
