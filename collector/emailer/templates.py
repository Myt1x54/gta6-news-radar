"""HTML email builders for breaking alerts and the daily digest.

Pure functions returning (subject, html) so they're easy to unit-test. Styles are
inline (email clients strip <style> blocks) and mobile-friendly.
"""

from __future__ import annotations

import html as _html
from typing import Any

from config import DASHBOARD_URL


def _esc(s: Any) -> str:
    return _html.escape(str(s)) if s is not None else ""


def _story_url(story: dict[str, Any]) -> str:
    return f"{DASHBOARD_URL}/story/{story['id']}"


def _story_block(story: dict[str, Any], idea: dict[str, Any] | None = None) -> str:
    rank = round(float(story.get("rank_score") or 0))
    cat = _esc((story.get("category") or "").replace("_", " "))
    vid = story.get("video_score")
    vid_txt = f"{vid}/10" if vid is not None else "–"
    summary = _esc(story.get("summary") or "")
    headline = _esc(story.get("headline") or "GTA 6 story")
    src = story.get("source_count") or 1

    idea_html = ""
    if idea:
        idea_html = (
            '<div style="margin-top:10px;padding:10px 12px;background:#f3f4f6;'
            'border-radius:8px;font-size:13px;color:#374151;">'
            f'<b>🎥 {_esc(idea.get("title"))}</b>'
            + (f'<br><span style="color:#6b7280;">{_esc(idea.get("hook"))}</span>' if idea.get("hook") else "")
            + "</div>"
        )

    return f"""
    <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:14px;">
      <div style="font-size:12px;color:#6b7280;margin-bottom:6px;">
        <span style="background:#eef2ff;color:#4338ca;border-radius:999px;padding:2px 8px;text-transform:capitalize;">{cat or "news"}</span>
        &nbsp;•&nbsp; rank <b style="color:#111827;">{rank}</b>
        &nbsp;•&nbsp; 🎬 {vid_txt}
        &nbsp;•&nbsp; {src} source{"s" if src != 1 else ""}
      </div>
      <a href="{_story_url(story)}" style="font-size:16px;font-weight:600;color:#111827;text-decoration:none;">{headline}</a>
      <div style="font-size:14px;color:#4b5563;margin-top:6px;line-height:1.45;">{summary}</div>
      {idea_html}
      <div style="margin-top:10px;">
        <a href="{_story_url(story)}" style="font-size:13px;color:#4f46e5;text-decoration:none;">Open in dashboard →</a>
      </div>
    </div>"""


def _wrap(title: str, intro: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f9fafb;">
  <div style="max-width:600px;margin:0 auto;padding:20px 16px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#111827;">
    <div style="font-size:20px;font-weight:700;margin-bottom:4px;">📡 {title}</div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:18px;">{intro}</div>
    {body}
    <div style="font-size:11px;color:#9ca3af;margin-top:20px;text-align:center;">
      GTA 6 News Radar · <a href="{DASHBOARD_URL}" style="color:#9ca3af;">open dashboard</a>
    </div>
  </div>
</body></html>"""


def render_alert_email(stories: list[dict[str, Any]]) -> tuple[str, str]:
    n = len(stories)
    if n == 1:
        subject = f"🚨 Breaking GTA 6: {stories[0].get('headline', 'new story')}"
        intro = "A high-scoring GTA 6 story just broke."
    else:
        subject = f"🚨 {n} breaking GTA 6 stories"
        intro = f"{n} high-scoring GTA 6 stories just broke."
    body = "".join(_story_block(s) for s in stories)
    return subject, _wrap("Breaking GTA 6", intro, body)


def render_digest_email(
    stories: list[dict[str, Any]],
    ideas_by_story: dict[str, dict[str, Any]] | None = None,
    trends: list[str] | None = None,
) -> tuple[str, str]:
    ideas_by_story = ideas_by_story or {}
    subject = f"📰 GTA 6 daily digest — top {len(stories)}"
    intro = "Your top GTA 6 stories from the last 24 hours."

    body = "".join(_story_block(s, ideas_by_story.get(s["id"])) for s in stories)
    if not stories:
        body = (
            '<div style="font-size:14px;color:#6b7280;">No notable GTA 6 stories in the '
            "last 24 hours.</div>"
        )

    if trends:
        items = "".join(f"<li>{_esc(t)}</li>" for t in trends[:8])
        body += (
            '<div style="margin-top:8px;font-size:14px;">'
            '<div style="font-weight:600;margin-bottom:6px;">🔥 Trending on YouTube</div>'
            f'<ul style="margin:0;padding-left:18px;color:#4b5563;">{items}</ul></div>'
        )

    return subject, _wrap("GTA 6 Daily Digest", intro, body)
