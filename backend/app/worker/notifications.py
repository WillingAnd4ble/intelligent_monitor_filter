"""
Notification dispatch for top-pick papers.

Supports Resend (email API) and Slack webhook. Both are optional —
if credentials are not configured, the respective channel is silently skipped.
"""

import json
import logging
import urllib.request
import requests as http_requests
from typing import List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_paper_summary_text(papers: List[Dict[str, Any]]) -> str:
    """Build a plain-text summary of top-ranked papers."""
    lines = [f"ArXiv Lens found {len(papers)} top pick(s) for you:\n"]
    for i, p in enumerate(papers, 1):
        score = p.get("agent_score", 0) or 0
        lines.append(f"{i}. [{score:.1f}/10] {p['title']}")
        if p.get("agent_explanation"):
            lines.append(f"   {p['agent_explanation'][:300]}")
        if p.get("source_url"):
            lines.append(f"   {p['source_url']}")
        lines.append("")
    return "\n".join(lines)


def _build_paper_summary_html(papers: List[Dict[str, Any]]) -> str:
    """Build an HTML email body for top-ranked papers."""
    rows = ""
    for p in papers:
        score = p.get("agent_score", 0) or 0
        explanation = p.get("agent_explanation", "") or ""
        source_url = p.get("source_url", "")
        url_line = f'<div style="font-size:12px;color:#6b7c4f;font-family:monospace;margin-top:4px;">{source_url}</div>' if source_url else ""
        rows += f"""
        <tr>
          <td style="padding:16px;border-bottom:1px solid #e2d9c8;">
            <div style="font-size:13px;font-weight:600;color:#6b7c4f;margin-bottom:4px;">{score:.1f} / 10</div>
            <div style="font-size:15px;font-weight:600;color:#1c1917;margin-bottom:6px;">{p['title']}</div>
            <div style="font-size:13px;color:#57534e;margin-bottom:8px;">{explanation[:400]}</div>
            {url_line}
          </td>
        </tr>"""

    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:Inter,Helvetica,Arial,sans-serif;background:#fcf9f3;padding:24px;">
      <div style="text-align:center;margin-bottom:24px;">
        <h1 style="font-size:20px;color:#454f33;margin:0;">ArXiv Lens</h1>
        <p style="font-size:14px;color:#78716c;margin:4px 0 0 0;">{len(papers)} top pick(s) from your latest pipeline run</p>
      </div>
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;border:1px solid #e2d9c8;">
        {rows}
      </table>
      <p style="font-size:12px;color:#78716c;text-align:center;margin-top:20px;">
        You're receiving this because you have notifications enabled in ArXiv Lens.
      </p>
    </div>"""


def send_email_notification(to_email: str, papers: List[Dict[str, Any]]) -> bool:
    """Send email notification via Resend API."""
    if not settings.RESEND_API_KEY:
        logger.debug("RESEND_API_KEY not configured — skipping email notification")
        return False

    try:
        resp = http_requests.post(
            "https://api.resend.com/emails",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            },
            json={
                "from": settings.RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": f"ArXiv Lens: {len(papers)} top pick(s) for you",
                "text": _build_paper_summary_text(papers),
                "html": _build_paper_summary_html(papers),
            },
            timeout=10,
        )
        resp.raise_for_status()
        resp_data = resp.json()
        logger.info(f"Email sent to {to_email} via Resend (id={resp_data.get('id')}, {len(papers)} papers)")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email} via Resend: {e}")
        return False


def _build_slack_blocks(papers: List[Dict[str, Any]]) -> list:
    """Build Slack Block Kit payload for rich notification."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"ArXiv Lens: {len(papers)} top pick(s) today"}
        }
    ]
    for p in papers[:10]:
        score = p.get("agent_score", 0) or 0
        text = f"*[{score:.1f}/10]* {p['title']}"
        if p.get("agent_explanation"):
            text += f"\n{p['agent_explanation'][:200]}"
        if p.get("source_url"):
            text += f"\n<{p['source_url']}|View on ArXiv>"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
        blocks.append({"type": "divider"})
    return blocks


def send_slack_notification(papers: List[Dict[str, Any]]) -> bool:
    """Send Slack notification via incoming webhook."""
    if not settings.SLACK_WEBHOOK_URL:
        logger.debug("Slack webhook not configured — skipping Slack notification")
        return False

    payload = json.dumps({
        "blocks": _build_slack_blocks(papers),
        "text": f"ArXiv Lens: {len(papers)} top pick(s) today"
    }).encode("utf-8")

    req = urllib.request.Request(
        settings.SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        urllib.request.urlopen(req)
        logger.info(f"Slack notification sent ({len(papers)} papers)")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def notify_top_picks(user_email: str, top_papers: List[Dict[str, Any]]):
    """Dispatch notifications to all configured channels."""
    if not top_papers:
        return

    send_email_notification(user_email, top_papers)
    send_slack_notification(top_papers)
