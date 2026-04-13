"""
Notification dispatch for top-ranked papers (FR17-FR18).

Supports email (SMTP) and Slack webhook. Both are optional —
if credentials are not configured, the respective channel is silently skipped.
"""

import json
import logging
import smtplib
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)

# Legacy threshold removed — top picks are now marked via is_top_pick=True in the pipeline


def _build_paper_summary(papers: List[Dict[str, Any]]) -> str:
    """Build a plain-text summary of top-ranked papers."""
    lines = [f"Your ArXiv Filter found {len(papers)} top pick(s) today:\n"]
    for i, p in enumerate(papers, 1):
        score = p.get("agent_score", 0) or 0
        lines.append(f"{i}. [{score:.1f}/10] {p['title']}")
        if p.get("agent_explanation"):
            lines.append(f"   {p['agent_explanation'][:200]}")
        if p.get("source_url"):
            lines.append(f"   {p['source_url']}")
        lines.append("")
    return "\n".join(lines)


def _build_slack_blocks(papers: List[Dict[str, Any]]) -> list:
    """Build Slack Block Kit payload for rich notification."""
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"ArXiv Filter: {len(papers)} top pick(s) today"}
        }
    ]
    for p in papers[:10]:  # Slack limits blocks
        score = p.get("agent_score", 0) or 0
        text = f"*[{score:.1f}/10]* {p['title']}"
        if p.get("agent_explanation"):
            text += f"\n{p['agent_explanation'][:200]}"
        if p.get("source_url"):
            text += f"\n<{p['source_url']}|View on ArXiv>"
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
        blocks.append({"type": "divider"})
    return blocks


def send_email_notification(to_email: str, papers: List[Dict[str, Any]]) -> bool:
    """Send email notification for top-ranked papers via SMTP."""
    if not all([settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD]):
        logger.debug("SMTP not configured — skipping email notification")
        return False

    body = _build_paper_summary(papers)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"ArXiv Filter: {len(papers)} top pick(s) for you"
    msg["From"] = settings.SMTP_USER
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info(f"Email notification sent to {to_email} ({len(papers)} papers)")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_slack_notification(papers: List[Dict[str, Any]]) -> bool:
    """Send Slack notification for top-ranked papers via incoming webhook."""
    if not settings.SLACK_WEBHOOK_URL:
        logger.debug("Slack webhook not configured — skipping Slack notification")
        return False

    payload = json.dumps({
        "blocks": _build_slack_blocks(papers),
        "text": f"ArXiv Filter: {len(papers)} top pick(s) today"  # fallback for plain clients
    }).encode("utf-8")

    req = urllib.request.Request(
        settings.SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        urllib.request.urlopen(req)
        logger.info(f"Slack notification sent ({len(papers)} papers)")
        return True
    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def notify_top_picks(user_email: str, top_papers: List[Dict[str, Any]]):
    """Dispatch notifications to all configured channels for top-ranked papers."""
    if not top_papers:
        return

    send_email_notification(user_email, top_papers)
    send_slack_notification(top_papers)
