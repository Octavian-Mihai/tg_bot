from __future__ import annotations

from datetime import datetime

from internbot.notifier import TELEGRAM_MAX_LEN
from internbot.ranking import Ranked
from internbot.terms import pretty_term


def format_job(rank: int, item: Ranked) -> str:
    job, score = item.job, item.score
    where = f" — {job.location}" if job.location else ""
    facts = [f"chance {score.chance}", f"quality {score.quality}"]
    term = pretty_term(job.term) or (job.term.title() if job.term in ("summer", "winter") else "")
    if term:
        facts.append(term)
    if score.pay:
        facts.append(score.pay)
    if score.tier != "unknown":
        facts.append(f"{score.tier}-tier")
    if score.matched_skills:
        facts.append("matches " + ", ".join(score.matched_skills[:4]))
    if score.confidence == "low":
        facts.append("title only")
    lines = [
        f"{rank}. {job.title}",
        f"   {job.company}{where}",
        f"   ⭐ {' · '.join(facts)}",
        f"   📄 Résumé: {item.resume.reason}",
    ]
    warnings = [f.replace("_", " ") for f in score.flags] + ([score.level_reason] if score.level_reason else [])
    if warnings:
        lines.append(f"   ⚠ {', '.join(warnings)}")
    lines.append(f"   {job.url}")
    return "\n".join(lines)


def format_messages(
    ranked: list[Ranked], queued: int = 0, footer: str = "", limit: int = TELEGRAM_MAX_LEN
) -> list[str]:
    """Batch ranked postings into as few messages as possible, never exceeding `limit` chars."""
    if not ranked:
        return []
    n = len(ranked)
    header = f"🆕 {n} new internship posting{'s' if n != 1 else ''}, best match first"
    if queued:
        header += f"\n({queued} more waiting; they arrive in the next check)"
    entries = [format_job(i, item) for i, item in enumerate(ranked, start=1)]
    if footer:
        entries.append(footer)
    messages: list[str] = []
    current = header
    for entry in entries:
        if len(entry) > limit:
            entry = entry[: limit - 1] + "…"
        candidate = f"{current}\n\n{entry}"
        if len(candidate) <= limit:
            current = candidate
        else:
            messages.append(current)
            current = entry
    messages.append(current)
    return messages


def format_empty(now: datetime, scanned: int, sources_ok: int, sources_failed: int, failed_names: list[str]) -> str:
    stamp = now.strftime("%a %b %d, %H:%M")
    text = (
        f"✅ internbot checked at {stamp}: no new internship postings.\n"
        f"Looked through {scanned} postings across {sources_ok} sources."
    )
    if sources_failed:
        text += f"\n⚠ {sources_failed} source(s) failed: {', '.join(failed_names[:6])}"
    return text


def sources_footer(sources_ok: int, sources_failed: int, failed_names: list[str]) -> str:
    text = f"Checked {sources_ok} sources"
    if sources_failed:
        text += f" ({sources_failed} failed: {', '.join(failed_names[:5])})"
    return text
