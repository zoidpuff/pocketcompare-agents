"""Build the sub-agent roster (AGENT_ROSTER.md + agent_roster.csv) from the exported PI transcript.

For every `Agent` tool call of the PI: launch time, short description, agent type, model, the agent id, how often it
was re-briefed (SendMessage), and the usage reported in its last completion notification (sub-agent tokens, tool
uses, wall time). Times are converted from UTC to CET (UTC+1). Reads only agent_logs/raw/ (already redacted).

    python scripts/meta/build_agent_roster.py --logs agent_logs --out .
"""
import argparse
import csv
import gzip
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

PHASES = [  # (start CET, label) — boundaries from RESEARCH_TREE.md milestones
    ("2026-10-27 18:00", "1 kickoff: literature, data, feasibility"),
    ("2026-10-27 19:05", "2 design review"),
    ("2026-10-27 19:20", "3 build: evaluation, splits, descriptors"),
    ("2026-10-27 21:00", "4 development and selection"),
    ("2026-10-28 03:40", "5 freeze, final evaluation, verification"),
    ("2026-10-28 05:35", "6 post-test: exploration, report, replication"),
    ("2026-10-28 08:30", "7 dissemination: cost, briefing, repositories"),
]


def phase(t: datetime) -> str:
    lab = PHASES[0][1]
    for s, l in PHASES:
        if t >= datetime.fromisoformat(s):
            lab = l
    return lab


def texts(content):
    if isinstance(content, str):
        yield content
    for c in content or []:
        if isinstance(c, dict):
            if c.get("type") == "text":
                yield c.get("text", "")
            elif c.get("type") == "tool_result":
                r = c.get("content")
                if isinstance(r, str):
                    yield r
                elif isinstance(r, list):
                    for x in r:
                        if isinstance(x, dict) and x.get("type") == "text":
                            yield x.get("text", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    recs = [json.loads(l) for l in gzip.open(a.logs / "raw" / "main_session_PI.jsonl.gz", "rt")]
    calls, by_tool = [], {}
    resumes, usage, notes = {}, {}, {}
    for r in recs:
        msg = r.get("message") or {}
        ts = r.get("timestamp")
        if r.get("type") == "assistant":
            for c in msg.get("content") or []:
                if c.get("type") == "tool_use" and c.get("name") == "Agent":
                    i = c.get("input", {})
                    rec = {"tool_use_id": c["id"], "time": ts, "description": i.get("description", ""),
                           "type": i.get("subagent_type", "general-purpose"), "model": i.get("model", "inherit"),
                           "prompt_chars": len(i.get("prompt", "")), "agent_id": None}
                    calls.append(rec)
                    by_tool[c["id"]] = rec
                elif c.get("type") == "tool_use" and c.get("name") == "SendMessage":
                    to = (c.get("input") or {}).get("to", "")
                    resumes[to] = resumes.get(to, 0) + 1
        for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in by_tool:
                for t in texts([c]):
                    m = re.search(r"agentId: ([a-f0-9]{17})", t)
                    if m:
                        by_tool[c["tool_use_id"]]["agent_id"] = m.group(1)
        extra = [r["content"]] if isinstance(r.get("content"), str) else []
        for t in list(texts(msg.get("content"))) + extra:
            for m in re.finditer(r"<task-id>([a-f0-9]{17})</task-id>.*?<usage><subagent_tokens>(\d+)</subagent_tokens>"
                                 r"<tool_uses>(\d+)</tool_uses><duration_ms>(\d+)</duration_ms></usage>", t, re.S):
                aid, tok, tu, ms = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
                notes.setdefault(aid, []).append((ts or "", tok, tu, ms))
    # tokens are cumulative across re-briefings; tool uses and wall time restart with each run. A run ends when
    # the next notification reports fewer tool uses (duplicate notifications within one run are non-decreasing).
    for aid, ns in notes.items():
        ns = sorted(set(ns))
        runs, last = [], None
        for _, tok, tu, ms in ns:
            if last is not None and tu >= last[1] and ms >= last[2]:
                runs[-1] = (tok, tu, ms)
            else:
                runs.append((tok, tu, ms))
            last = (tok, tu, ms)
        usage[aid] = (max(r[0] for r in runs), sum(r[1] for r in runs), sum(r[2] for r in runs))
    rows = []
    for n, c in enumerate(calls, 1):
        t = datetime.fromisoformat(c["time"].replace("Z", "+00:00")).replace(tzinfo=None) + timedelta(hours=1)
        aid = c["agent_id"] or ""
        meta_f = a.logs / "raw" / "subagents" / f"agent-{aid}.meta.json"
        meta = json.loads(meta_f.read_text()) if meta_f.exists() else {}
        tok, tu, ms = usage.get(aid, (None, None, None))
        rows.append({"n": n, "launched_CET": t.strftime("%d %b %H:%M"), "phase": phase(t),
                     "description": c["description"], "agent_type": c["type"],
                     "model": meta.get("model") or c["model"], "agent_id": aid, "rebriefs": resumes.get(aid, 0),
                     "subagent_tokens": tok, "tool_uses": tu, "minutes": round(ms / 60000, 1) if ms else None,
                     "prompt_chars": c["prompt_chars"],
                     "log": f"agent_logs/readable/subagents/agent-{aid}.md" if aid else ""})
    # agents launched by other agents (spawn depth 2): only in the sub-agent meta files
    known = {r["agent_id"] for r in rows}
    for mf in sorted((a.logs / "raw" / "subagents").glob("agent-*.meta.json")):
        aid = mf.name[len("agent-"):-len(".meta.json")]
        meta = json.loads(mf.read_text())
        if aid in known:
            continue
        rec = [json.loads(l) for l in gzip.open(mf.with_name(f"agent-{aid}.jsonl.gz"), "rt")]
        t0 = datetime.fromisoformat(rec[0]["timestamp"].replace("Z", "+00:00")).replace(tzinfo=None) + timedelta(hours=1)
        parent = next((r["n"] for r in rows if r["agent_id"] == meta.get("parentAgentId")), "?")
        rows.append({"n": f"{parent}.{sum(1 for r in rows if str(r['n']).startswith(f'{parent}.')) + 1}",
                     "launched_CET": t0.strftime("%d %b %H:%M"), "phase": phase(t0),
                     "description": meta.get("description", "") + f" (launched by agent #{parent})",
                     "agent_type": meta.get("agentType", ""), "model": meta.get("model") or "inherit",
                     "agent_id": aid, "rebriefs": 0, "subagent_tokens": None, "tool_uses": None, "minutes": None,
                     "prompt_chars": None, "log": f"agent_logs/readable/subagents/agent-{aid}.md"})
    with open(a.out / "agent_roster.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tot_tok = sum(r["subagent_tokens"] or 0 for r in rows)
    tot_min = sum(r["minutes"] or 0 for r in rows)
    by_model = {}
    for r in rows:
        by_model[r["model"]] = by_model.get(r["model"], 0) + 1
    lines = ["# Sub-agent roster", "",
             f"Generated by `scripts/meta/build_agent_roster.py` from the PI transcript. {len(rows)} sub-agents ran "
             f"({sum(1 for r in rows if '.' not in str(r['n']))} launched by the PI, the rest by other agents); models: " + ", ".join(f"{k} × {v}" for k, v in sorted(by_model.items())) + ". "
             f"Summed sub-agent tokens (last completion report of each agent, cumulative over re-briefings): "
             f"{tot_tok / 1e6:.1f} M; summed sub-agent wall time {tot_min / 60:.1f} h (agents ran in parallel). "
             "Times are CET. *Re-briefs* = follow-up messages from the PI to the same agent.", "",
             "| # | launched | phase | task | model | re-briefs | tokens (k) | tool uses | minutes | log |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['n']} | {r['launched_CET']} | {r['phase']} | {r['description']} | {r['model']} | "
                     f"{r['rebriefs']} | {'' if r['subagent_tokens'] is None else round(r['subagent_tokens'] / 1000)} | "
                     f"{r['tool_uses'] or ''} | {r['minutes'] or ''} | [log]({r['log']}) |")
    (a.out / "AGENT_ROSTER.md").write_text("\n".join(lines) + "\n")
    print(len(rows), "agents;", f"{tot_tok / 1e6:.1f} M tokens;", by_model,
          "missing ids:", sum(1 for r in rows if not r["agent_id"]), "missing usage:",
          sum(1 for r in rows if r["subagent_tokens"] is None))


if __name__ == "__main__":
    main()
