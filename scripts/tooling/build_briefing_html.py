"""Render the research briefing (release/pocketcompare/docs/BRIEFING.md) as one self-contained HTML page.

Figures are embedded as data URIs; HTML comments (number sources) are kept in the page source.

    python scripts/tooling/build_briefing_html.py --md release/pocketcompare/docs/BRIEFING.md --out /tmp/briefing.html
"""
import argparse
import base64
import re
from pathlib import Path

import markdown

CSS = """
/* Layout: one reading column (~70ch) with a sticky contents rail on wide screens; figures break out wider. */
:root {
  --paper: #f7f8f9; --ink: #1b2430; --muted: #5b6672; --rule: #d9dee4; --panel: #eef1f4;
  --accent: #2a6bd1; --warm: #d9622b; --plate: #fcfcfb;
  --serif: "Newsreader", Georgia, "Times New Roman", serif;
  --sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #12161c; --ink: #e3e7ec; --muted: #9aa5b1; --rule: #2b333d; --panel: #1a2029;
  --accent: #7ba7f0; --warm: #f08c5a; --plate: #f4f4f2; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #12161c; --ink: #e3e7ec; --muted: #9aa5b1; --rule: #2b333d; --panel: #1a2029;
  --accent: #7ba7f0; --warm: #f08c5a; --plate: #f4f4f2; color-scheme: dark }
body { background: var(--paper); color: var(--ink); font-family: var(--serif); font-size: 18px; line-height: 1.6; }
.wrap { display: grid; grid-template-columns: minmax(0, 1fr); gap: 48px; max-width: 1240px; margin: 0 auto;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 40px 96px; }
@media (min-width: 1100px) { .wrap { grid-template-columns: 220px minmax(0, 1fr); } }
nav.toc { display: none; font-family: var(--sans); font-size: 13px; line-height: 1.4; }
@media (min-width: 1100px) { nav.toc { display: block; position: sticky; top: calc(env(safe-area-inset-top, 0px) + 24px);
  align-self: start; max-height: calc(100vh - 48px); overflow-y: auto; } }
nav.toc p { text-transform: uppercase; letter-spacing: .08em; font-size: 11px; color: var(--muted); margin: 0 0 10px; }
nav.toc ol { list-style: none; padding: 0; margin: 0; display: grid; gap: 7px; }
nav.toc a { color: var(--muted); text-decoration: none; }
nav.toc a:hover, nav.toc a:focus-visible { color: var(--accent); }
main { min-width: 0; }
article { max-width: 70ch; }
header.masthead { max-width: 70ch; margin-bottom: 8px; }
.eyebrow { font-family: var(--sans); font-size: 12px; letter-spacing: .1em; text-transform: uppercase; color: var(--accent); margin: 0 0 14px; }
h1 { font-family: var(--serif); font-weight: 600; font-size: clamp(30px, 4.2vw, 44px); line-height: 1.12; letter-spacing: -.01em; text-wrap: balance; margin: 0 0 18px; }
h2 { font-family: var(--sans); font-weight: 600; font-size: 24px; line-height: 1.25; text-wrap: balance; margin: 56px 0 14px; padding-top: 14px; border-top: 1px solid var(--rule); }
h3 { font-family: var(--sans); font-weight: 600; font-size: 18px; margin: 34px 0 10px; }
p, li { text-wrap: pretty; }
a { color: var(--accent); }
strong { font-weight: 600; }
code { font-family: var(--mono); font-size: .82em; background: var(--panel); padding: .08em .3em; border-radius: 3px; }
hr { display: none; }
ul, ol { padding-left: 1.3em; }
li + li { margin-top: .35em; }
.standfirst { font-style: italic; color: var(--muted); font-size: 16px; }
.tablewrap { overflow-x: auto; margin: 22px 0; max-width: 100%; }
table { border-collapse: collapse; font-family: var(--sans); font-size: 14px; line-height: 1.4; min-width: 100%;
  font-variant-numeric: tabular-nums; }
th { text-align: left; font-weight: 600; border-bottom: 2px solid var(--ink); padding: 8px 10px; vertical-align: bottom; }
td { border-bottom: 1px solid var(--rule); padding: 8px 10px; vertical-align: top; }
section.box { background: var(--panel); border-radius: 6px; padding: 4px 22px 14px; margin: 40px 0; }
section.box h2 { border-top: 0; margin-top: 18px; padding-top: 0; font-size: 19px; }
section.box table { font-size: 13.5px; }
figure { margin: 36px 0 40px; width: min(100%, 1000px); }
@media (min-width: 1100px) { figure { width: min(calc(100% + 0px), 1000px); } }
figure .plate { background: var(--plate); border: 1px solid var(--rule); border-radius: 6px; padding: 10px; }
figure img { display: block; width: 100%; height: auto; }
figcaption { font-family: var(--sans); font-size: 14px; line-height: 1.5; color: var(--muted); margin-top: 12px; max-width: 78ch; }
figcaption strong { color: var(--ink); }
.refs ol { font-family: var(--sans); font-size: 13.5px; line-height: 1.45; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&'
         'family=IBM+Plex+Sans:wght@400;600&family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&display=swap">')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    md = a.md.read_text()
    title_line = md.splitlines()[0].lstrip("# ").strip()
    body_md = "\n".join(md.splitlines()[1:])
    html = markdown.markdown(body_md, extensions=["tables", "toc", "sane_lists"])

    def embed(m):
        p = a.md.parent / m.group(1)
        return f'src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}"'
    html = re.sub(r'src="(figures/[^"]+\.png)"', embed, html)
    # image paragraph + caption paragraph -> <figure>
    html = re.sub(r'<p><img alt="([^"]*)" (src="[^"]+") /></p>\s*<p>(<strong>Figure \d.*?)</p>',
                  r'<figure><div class="plate"><img alt="\1" \2 loading="lazy"></div><figcaption>\3</figcaption></figure>',
                  html, flags=re.S)
    html = re.sub(r"(<table>.*?</table>)", r'<div class="tablewrap">\1</div>', html, flags=re.S)
    # glossary box
    html = re.sub(r'(<h2 id="box-1-glossary">.*?</h2>\s*<div class="tablewrap">.*?</div>)',
                  r'<section class="box">\1</section>', html, flags=re.S)
    html = re.sub(r'(<h2 id="references">.*)', r'<div class="refs">\1</div>', html, flags=re.S)
    # first italic paragraph = standfirst
    html = html.replace("<p><em>", '<p class="standfirst"><em>', 1)
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html)
    toc = "".join(f'<li><a href="#{i}">{re.sub("<.*?>", "", t)}</a></li>' for i, t in heads)
    page = f"""<title>pocketcompare Research Briefing</title>
<meta name="claude:viewport-fit-sides" content="cover">
{FONTS}
<style>{CSS}</style>
<div class="wrap">
<nav class="toc" aria-label="Contents"><p>Contents</p><ol>{toc}</ol></nav>
<main>
<header class="masthead"><p class="eyebrow">Research briefing · protein pocket similarity · agentic science</p>
<h1>{title_line}</h1></header>
<article>
{html}
</article>
</main>
</div>
"""
    a.out.write_text(page)
    print(a.out, round(len(page) / 1e6, 2), "MB,", len(heads), "sections,", page.count("<figure>"), "figures")


if __name__ == "__main__":
    main()
