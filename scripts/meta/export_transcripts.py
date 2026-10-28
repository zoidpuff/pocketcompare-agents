"""Export the Claude Code session transcripts of the project (PI agent + all sub-agents) for publication.

What is kept: the conversation records (user / assistant messages incl. tool calls and tool results, attachments,
queue operations) and the session's cost record. What is dropped: harness bookkeeping records that duplicate the
conversation or carry account identifiers (api-request*, bridge-session, file-history*, atis-latch, frame-link,
artifact-*). Redactions applied to every exported line:
  * the session owner's private e-mail (--email-from) -> the public address chosen by the owner (--email-to);
  * ProSPECCTs pair-label rows (e.g. "1eyn,1ow4,active"), because the ProSPECCTs licence forbids redistribution;
  * any account / organisation UUID field that might remain.
Outputs: agent_logs/raw/ (gzipped JSONL, one file per agent, + sub-agent meta.json + persisted tool outputs) and
agent_logs/readable/ (Markdown renderings with long tool outputs truncated). A redaction summary is printed and
written to agent_logs/EXPORT.json.

    python scripts/meta/export_transcripts.py --session <~/.claude/projects/.../SESSION_ID> --out agent_logs \
        --email-from <private address> --email-to <public address>
"""
import argparse
import gzip
import json
import re
from pathlib import Path

KEEP = {"user", "assistant", "attachment", "queue-operation", "cost-state"}
EMAIL_FROM, EMAIL_TO = "", ""  # set from --email-from / --email-to
PROSPECCTS_ROW = re.compile(r"(?:(?<=\\n)|(?<=\\t)|(?<![A-Za-z0-9_.\\]))[A-Za-z0-9_.]{4,8}[,; \t]+[A-Za-z0-9_.]{4,8}"
                            r"[,; \t]+(?:active|inactive)(?![A-Za-z])")
UUID_FIELD = re.compile(r'("(?:owner)?(?:Account|Organization|account|organization)Uuid"\s*:\s*")[0-9a-f-]{36}(")')
TRUNC = 1500


def redact(line: str, stats: dict) -> str:
    n = line.count(EMAIL_FROM) if EMAIL_FROM else 0
    if n:
        stats["email"] += n
        line = line.replace(EMAIL_FROM, EMAIL_TO)
    line, k = PROSPECCTS_ROW.subn("[ProSPECCTs pair row redacted: licence forbids redistribution]", line)
    stats["prospeccts_rows"] += k
    line, k = UUID_FIELD.subn(r"\1<redacted>\2", line)
    stats["uuid_fields"] += k
    return line


def export_jsonl(src: Path, dst: Path, stats: dict) -> list[dict]:
    kept = []
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src) as fi, gzip.open(dst, "wt") as fo:
        for line in fi:
            if not line.strip():
                continue
            t = json.loads(line).get("type")
            if t not in KEEP:
                stats["dropped_records"] += 1
                continue
            line = redact(line, stats)
            fo.write(line if line.endswith("\n") else line + "\n")
            kept.append(json.loads(line))
    return kept


def _short(x, n=TRUNC):
    s = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + f"\n… [{len(s) - n:,} more characters; full text in agent_logs/raw/]"


def render(records: list[dict], title: str) -> str:
    out = [f"# {title}\n", "Rendered from the raw transcript (agent_logs/raw/). Tool inputs and outputs are truncated to "
           f"{TRUNC:,} characters; assistant text is complete. Thinking blocks are included where stored as text.\n"]
    for r in records:
        t, msg, ts = r.get("type"), r.get("message") or {}, (r.get("timestamp") or "")[:19].replace("T", " ")
        if t == "cost-state":
            out.append(f"\n---\n**Cost record** ({ts}): total ≈ ${r.get('totalCostUSD', 0):,.2f}\n")
            continue
        if t not in ("user", "assistant"):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        for c in content or []:
            ct = c.get("type")
            if ct == "text" and c.get("text", "").strip():
                who = "PI / user turn" if t == "user" else "Assistant"
                body = c["text"] if t == "assistant" else _short(c["text"], 6000)
                out.append(f"\n### {who} · {ts}\n\n{body}\n")
            elif ct == "thinking" and c.get("thinking", "").strip():
                out.append(f"\n<details><summary>thinking · {ts}</summary>\n\n{_short(c['thinking'], 4000)}\n\n</details>\n")
            elif ct == "tool_use":
                out.append(f"\n**→ tool call `{c.get('name')}`** · {ts}\n\n```\n{_short(c.get('input'))}\n```\n")
            elif ct == "tool_result":
                res = c.get("content")
                if isinstance(res, list):
                    res = "\n".join(x.get("text", "[non-text content]") for x in res if isinstance(x, dict))
                out.append(f"\n**← tool result**\n\n```\n{_short(res or '')}\n```\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", type=Path, required=True, help="session directory (its .jsonl sits next to it)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--email-from", required=True, help="address to replace (the session owner's private address)")
    ap.add_argument("--email-to", required=True, help="public replacement address")
    a = ap.parse_args()
    global EMAIL_FROM, EMAIL_TO
    EMAIL_FROM, EMAIL_TO = a.email_from, a.email_to
    stats = {"email": 0, "prospeccts_rows": 0, "uuid_fields": 0, "dropped_records": 0}
    raw, readable = a.out / "raw", a.out / "readable"
    main_rec = export_jsonl(a.session.with_suffix(".jsonl"), raw / "main_session_PI.jsonl.gz", stats)
    readable.mkdir(parents=True, exist_ok=True)
    (readable / "main_session_PI.md").write_text(render(main_rec, "PI agent — main session"))
    n_sub = 0
    for f in sorted((a.session / "subagents").glob("agent-*.jsonl")):
        rec = export_jsonl(f, raw / "subagents" / (f.stem + ".jsonl.gz"), stats)
        meta_f = f.with_name(f.stem + ".meta.json")
        meta = json.loads(redact(meta_f.read_text(), stats)) if meta_f.exists() else {}
        (raw / "subagents" / meta_f.name).write_text(json.dumps(meta, indent=1))
        (readable / "subagents").mkdir(exist_ok=True)
        (readable / "subagents" / (f.stem + ".md")).write_text(
            render(rec, f"Sub-agent {f.stem.removeprefix('agent-')} — {meta.get('description', '')} "
                        f"({meta.get('model', '?')})"))
        n_sub += 1
    tr = a.session / "tool-results"
    if tr.exists():
        for f in sorted(tr.iterdir()):
            dst = raw / "tool-results" / (f.name + ".gz")
            dst.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(dst, "wt") as fo:
                fo.write(redact(f.read_text(errors="replace"), stats))
    stats["n_subagents"] = n_sub
    (a.out / "EXPORT.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
