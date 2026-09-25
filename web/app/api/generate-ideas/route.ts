import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

// Server-side "Generate more ideas": calls Gemini (Groq fallback) with the AI
// key kept on the server, then inserts new video_ideas for the story.

const FORMATS = [
  "news_breakdown",
  "reaction",
  "theory",
  "everything_we_know",
  "comparison",
  "short",
];

function buildPrompt(story: {
  headline: string;
  summary: string | null;
  category: string | null;
}): string {
  return `You brainstorm YouTube video ideas for a GTA 6 news channel.
Story headline: ${story.headline}
Summary: ${story.summary ?? ""}
Category: ${story.category ?? "other"}

Return ONLY JSON: {"ideas":[{"title":"YouTube-style title","hook":"first 10 seconds","format":"news_breakdown|reaction|theory|everything_we_know|comparison|short","angle":"one line"}]}
Give exactly 3 fresh ideas, different from obvious ones.`;
}

async function callGemini(prompt: string): Promise<string> {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new Error("no gemini key");
  const model = process.env.GEMINI_MODEL || "gemini-3.5-flash-lite";
  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-goog-api-key": key },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { responseMimeType: "application/json", temperature: 0.9 },
      }),
    },
  );
  if (!res.ok) throw new Error(`gemini ${res.status}`);
  const data = await res.json();
  return data?.candidates?.[0]?.content?.parts?.[0]?.text ?? "";
}

async function callGroq(prompt: string): Promise<string> {
  const key = process.env.GROQ_API_KEY;
  if (!key) throw new Error("no groq key");
  const model = process.env.GROQ_MODEL || "openai/gpt-oss-120b";
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model,
      messages: [{ role: "user", content: prompt }],
      response_format: { type: "json_object" },
      temperature: 0.9,
    }),
  });
  if (!res.ok) throw new Error(`groq ${res.status}`);
  const data = await res.json();
  return data?.choices?.[0]?.message?.content ?? "";
}

function stripFences(t: string): string {
  return t.replace(/^\s*```(?:json)?\s*/i, "").replace(/\s*```\s*$/i, "").trim();
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const { storyId } = await request.json().catch(() => ({}));
  if (!storyId) return NextResponse.json({ error: "missing storyId" }, { status: 400 });

  const { data: story } = await supabase
    .from("stories")
    .select("id,headline,summary,category")
    .eq("id", storyId)
    .single();
  if (!story) return NextResponse.json({ error: "story not found" }, { status: 404 });

  const prompt = buildPrompt(story);
  let raw: string;
  try {
    raw = await callGemini(prompt);
  } catch {
    try {
      raw = await callGroq(prompt);
    } catch {
      return NextResponse.json({ error: "AI unavailable" }, { status: 502 });
    }
  }

  let ideas: unknown;
  try {
    ideas = JSON.parse(stripFences(raw))?.ideas;
  } catch {
    return NextResponse.json({ error: "bad AI response" }, { status: 502 });
  }
  if (!Array.isArray(ideas) || ideas.length === 0) {
    return NextResponse.json({ error: "no ideas" }, { status: 502 });
  }

  const rows = ideas
    .filter((i): i is Record<string, string> => !!i && typeof i === "object" && "title" in i)
    .slice(0, 3)
    .map((i) => ({
      story_id: storyId,
      title: String(i.title).slice(0, 300),
      hook: i.hook ? String(i.hook) : null,
      format: FORMATS.includes(String(i.format)) ? String(i.format) : "news_breakdown",
      angle: i.angle ? String(i.angle) : null,
      generated_on_demand: true,
    }));

  if (rows.length === 0) {
    return NextResponse.json({ error: "no valid ideas" }, { status: 502 });
  }

  const { error } = await supabase.from("video_ideas").insert(rows);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ inserted: rows.length });
}
