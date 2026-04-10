"""Email service — Gmail SMTP.

Sends HTML emails for:
1. Welcome + top opportunities on first login
2. Weekly digest of best-fit hackathons
3. Bridge roadmap on hackathon registration

All sends are fire-and-forget (async, non-blocking). If SMTP isn't configured,
calls silently no-op so the app works without email.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from astra_api.settings import settings
from astra_schemas import Opportunity, UserProfile

logger = logging.getLogger("astra.email")


def _is_configured() -> bool:
    return bool(settings.smtp_user and settings.smtp_password)


def _send_html_email(to: str, subject: str, html: str) -> None:
    """Synchronous SMTP send. Call from asyncio.to_thread()."""
    if not _is_configured():
        logger.info("Email not configured — skipping send to %s", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(msg["From"], [to], msg.as_string())
        logger.info("Email sent to %s: %s", to, subject)
    except Exception as exc:
        logger.error("Email send failed to %s: %s", to, exc)


async def send_email_async(to: str, subject: str, html: str) -> None:
    """Non-blocking email send."""
    await asyncio.to_thread(_send_html_email, to, subject, html)


# ---------------------------------------------------------------------------
# Email templates
# ---------------------------------------------------------------------------


def _opp_card_html(opp: Opportunity, rank: int) -> str:
    deadline = opp.metadata.deadline_iso
    deadline_str = deadline.strftime("%b %d, %Y") if isinstance(deadline, datetime) else str(deadline)
    fit = opp.match_analysis.overall_fit_percentage
    color = "#10b981" if fit >= 60 else "#f59e0b" if fit >= 40 else "#6b7280"
    skills = ", ".join(opp.metadata.raw_requirements[:5]) or "General"
    return f"""
    <tr>
      <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">
        <div style="font-size:13px;color:#6b7280;">#{rank}</div>
        <div style="font-size:16px;font-weight:600;color:#111827;">{opp.metadata.title}</div>
        <div style="font-size:13px;color:#6b7280;margin-top:2px;">
          {opp.metadata.organization} &middot; {opp.metadata.source} &middot; Deadline: {deadline_str}
        </div>
        <div style="font-size:12px;color:#6b7280;margin-top:4px;">Skills: {skills}</div>
        <div style="margin-top:6px;">
          <span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;color:white;background:{color};">
            {fit}% fit
          </span>
        </div>
      </td>
    </tr>
    """


def build_welcome_email(user: UserProfile, top_opps: list[Opportunity]) -> str:
    """Welcome email with top personalized opportunities."""
    name = user.github_name or user.github_login
    opp_rows = "".join(_opp_card_html(o, i + 1) for i, o in enumerate(top_opps[:10]))

    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="background:#4f46e5;padding:32px 24px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;font-size:24px;margin:0;">Welcome to Astra</h1>
        <p style="color:#c7d2fe;font-size:14px;margin:8px 0 0;">Opportunity, On-Target.</p>
      </div>
      <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none;">
        <p style="font-size:15px;color:#374151;">Hi {name},</p>
        <p style="font-size:14px;color:#6b7280;line-height:1.6;">
          Your Astra account is set up. We've analyzed your profile and found
          the hackathons that best match your skills. Here are your top picks:
        </p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          {opp_rows}
        </table>
        <p style="font-size:13px;color:#6b7280;margin-top:16px;">
          You'll receive a weekly digest with new opportunities matched to your profile.
          Click any hackathon in the app to see your skill gap analysis, bridge roadmap,
          and scaffold a starter repo.
        </p>
      </div>
      <div style="padding:16px 24px;font-size:12px;color:#9ca3af;text-align:center;">
        Astra — Multi-agent AI hackathon co-pilot
      </div>
    </div>
    """


def build_digest_email(user: UserProfile, opps: list[Opportunity]) -> str:
    """Weekly digest email with top opportunities."""
    name = user.github_name or user.github_login
    opp_rows = "".join(_opp_card_html(o, i + 1) for i, o in enumerate(opps[:10]))
    now = datetime.now(timezone.utc).strftime("%b %d, %Y")

    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="background:#4f46e5;padding:24px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;font-size:20px;margin:0;">Your Weekly Hackathon Digest</h1>
        <p style="color:#c7d2fe;font-size:13px;margin:4px 0 0;">{now}</p>
      </div>
      <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none;">
        <p style="font-size:14px;color:#374151;">Hi {name}, here are this week's best-fit opportunities:</p>
        <table style="width:100%;border-collapse:collapse;margin:16px 0;">
          {opp_rows}
        </table>
      </div>
      <div style="padding:16px 24px;font-size:12px;color:#9ca3af;text-align:center;">
        Astra — Opportunity, On-Target.
      </div>
    </div>
    """


def build_registration_email(
    user: UserProfile, opp: Opportunity
) -> str:
    """Email sent when a user registers for a hackathon — includes the bridge roadmap."""
    name = user.github_name or user.github_login
    deadline = opp.metadata.deadline_iso
    deadline_str = deadline.strftime("%b %d, %Y") if isinstance(deadline, datetime) else str(deadline)

    roadmap_html = ""
    for day in opp.readiness_engine.bridge_roadmap[:7]:
        resources = "".join(
            f'<li style="margin:2px 0;"><a href="{r.url}" style="color:#4f46e5;text-decoration:none;">[{r.type}] {r.title}</a></li>'
            for r in day.resources
        )
        roadmap_html += f"""
        <div style="margin-bottom:12px;padding:12px;border:1px solid #e5e7eb;border-radius:8px;">
          <div style="font-size:12px;font-weight:600;color:#4f46e5;">Day {day.day}</div>
          <div style="font-size:14px;font-weight:500;color:#111827;">{day.focus}</div>
          <ul style="margin:6px 0 0;padding-left:16px;font-size:13px;">{resources}</ul>
        </div>
        """

    gap_tags = " ".join(
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;background:#fee2e2;color:#991b1b;margin:2px;">{s}</span>'
        for s in opp.readiness_engine.skill_gap_identified
    )

    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="background:#059669;padding:24px;border-radius:12px 12px 0 0;">
        <h1 style="color:white;font-size:20px;margin:0;">You're registered!</h1>
        <p style="color:#d1fae5;font-size:14px;margin:4px 0 0;">{opp.metadata.title}</p>
      </div>
      <div style="background:white;padding:24px;border:1px solid #e5e7eb;border-top:none;">
        <p style="font-size:14px;color:#374151;">Hi {name},</p>
        <p style="font-size:14px;color:#6b7280;">
          You've registered for <strong>{opp.metadata.title}</strong> by {opp.metadata.organization}.
          Deadline: <strong>{deadline_str}</strong>.
        </p>

        <h2 style="font-size:16px;color:#111827;margin:20px 0 8px;">Your skill gap</h2>
        <div>{gap_tags or '<span style="color:#059669;">No gaps - you are ready!</span>'}</div>

        <h2 style="font-size:16px;color:#111827;margin:20px 0 8px;">Your 7-day bridge roadmap</h2>
        {roadmap_html or '<p style="color:#059669;">No roadmap needed — your skills already cover the requirements.</p>'}

        <p style="font-size:13px;color:#6b7280;margin-top:20px;">
          Open the app to scaffold a starter repo and rehearse your demo day pitch.
        </p>
      </div>
      <div style="padding:16px 24px;font-size:12px;color:#9ca3af;text-align:center;">
        Astra — Opportunity, On-Target.
      </div>
    </div>
    """
