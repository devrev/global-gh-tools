"""Rendering contract for the Service Policy pull request comment.

This module is shared by two producers of the same comment: the org-level
`service-policy-check` workflow in this repository, and the scheduled job that
refreshes open pull requests when a repository's results change. The second
copy is vendored byte for byte, so this file must stay self-contained and use
the Python standard library only (no boto3, no GitHub client).

Contract summary:

- The comment body starts with MARKER on its own first line.
- Visible results are the results whose policy mode is warn or block. Block
  is rendered as warn in this version; observe results are never shown.
- The rendered hash is the sha256 hex digest of
  json.dumps(visible_results, sort_keys=True, separators=(",", ":")), and the
  empty list hashes to "".
- Every field taken from Constellation or a feed is escaped so it renders as
  literal text, and `::` is neutralized so it cannot read as a workflow
  command. A remediation link is rendered as a link only when it is https.
"""

import hashlib
import json
import re
from urllib.parse import quote

MARKER = "<!-- service-policy-check -->"
HEADING = "Service Policy check (warning only)"
VISIBLE_MODES = ("warn", "block")
OUTCOME_LABELS = {
    "violate": "violates",
    "unknown": "status unknown",
    "exempt": "exempt",
}
HELP_LINE = (
    "This check is warning only and never blocks a merge. Each entry is a "
    "governance policy declared in Constellation for a service this "
    "repository backs. To resolve one, follow its remediation link or "
    "contact its owner."
)

# Characters with markdown or inline-HTML meaning in GitHub comments.
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|<>~&=:\"'])")
_WHITESPACE = re.compile(r"\s+")
# Zero-width space placed between the colons of `::`.
_ZWSP = "​"


def visible_results(results):
    """Return the results shown on pull requests, in their original order."""
    return [
        r for r in (results or []) if (r.get("policy") or {}).get("mode") in VISIBLE_MODES
    ]


def rendered_hash(visible):
    """Return the hash of the visible results, or "" when there are none."""
    if not visible:
        return ""
    payload = json.dumps(visible, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def neutralize_commands(value):
    """Break every `::` so the text cannot be read as a workflow command."""
    text = "" if value is None else str(value)
    while "::" in text:
        text = text.replace("::", ":" + _ZWSP + ":")
    return text


def escape_markdown(value):
    """Render an untrusted field as literal, single-line markdown text."""
    text = _WHITESPACE.sub(" ", "" if value is None else str(value)).strip()
    text = _MARKDOWN_SPECIAL.sub(r"\\\1", text)
    return neutralize_commands(text)


def render_link(url, text="remediation"):
    """Render url as a markdown link only when it is https; else as text."""
    url = "" if url is None else str(url).strip()
    if not url:
        return "none provided"
    if not url.startswith("https://"):
        return escape_markdown(url) + " (not a link: only https links are rendered)"
    safe_url = neutralize_commands(
        quote(url, safe=":/?#@!$&*+,;=%~-._")
    )
    return "[" + escape_markdown(text) + "](" + safe_url + ")"


def render_entry(result):
    policy = result.get("policy") or {}
    outcome = result.get("outcome")
    label = OUTCOME_LABELS.get(outcome, escape_markdown(outcome))
    team = result.get("team") or ""
    lines = [
        "- **" + escape_markdown(policy.get("reason")) + "**",
        "  - Service: " + escape_markdown(result.get("service")),
        "  - Team: " + (escape_markdown(team) if team else "not recorded"),
        "  - Outcome: " + label,
        "  - Owner: " + escape_markdown(policy.get("owner")),
        "  - Remediation: " + render_link(policy.get("remediation_url")),
    ]
    return "\n".join(lines)


def render_comment(visible):
    """Return the full comment body for a non-empty list of visible results."""
    parts = [MARKER, "## " + HEADING, ""]
    for result in visible:
        parts.append(render_entry(result))
    parts.append("")
    parts.append(HELP_LINE)
    return "\n".join(parts) + "\n"
