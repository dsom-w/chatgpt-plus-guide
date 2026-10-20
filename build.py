#!/usr/bin/env python3
"""Build the GitHub Pages site.

  README.md      -> index.html            (home)
  pages/<x>.md   -> <slug>/index.html     (one page per search intent)

Run `python3 build.py` after editing any .md, then commit. The Actions
workflow runs it on every push, so committing index.html is optional.
Requires: pip install markdown
"""
import glob
import html
import json
import os
import re
import unicodedata
from datetime import date

import markdown
from markdown.extensions.toc import TocExtension

SITE_URL = "https://dsom-w.github.io/chatgpt-plus-guide/"
REPO_URL = "https://github.com/dsom-w/chatgpt-plus-guide"
OG_IMAGE = SITE_URL + "images/chatgpt/1-1-plans.webp"
PUBLISHED = "2026-10-20"

HOME = {
    "slug": "",
    "nav": "ChatGPT Plus 开通总览",
    # Google shows roughly 30 CJK characters of a title; keep the front loaded.
    "title": "ChatGPT Plus 国内开通 2026：支付宝微信 3 分钟充值，四种方法对比",
    "description": (
        "没有海外卡怎么开 ChatGPT Plus？2026 年国内四条路线逐条对比成本与风险："
        "官方直付、虚拟卡、美区礼品卡、代充；附支付宝 / 微信 3 分钟自助充值实测截图，"
        "不要密码、不换号，Claude Pro 同样适用。"
    ),
    "keywords": (
        "ChatGPT Plus 国内开通, ChatGPT Plus 支付宝, ChatGPT Plus 微信支付, ChatGPT 代充, "
        "ChatGPT Plus 充值, ChatGPT Plus 怎么买, 国内开通 ChatGPT Plus, Claude Pro 国内开通, "
        "美区礼品卡 ChatGPT, 虚拟信用卡 ChatGPT"
    ),
    "cta": "支付宝 / 微信 3 分钟开通 ChatGPT Plus · 不要密码 · 不成功原路退款",
    "cta_url": "https://okai66.com/?utm_source=github&utm_medium=pages&utm_campaign=sticky-home",
}


# ---------- helpers ----------

def github_slug(text: str) -> str:
    """Mimic GitHub's heading anchors so README links keep working."""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return text.replace(" ", "-")


def parse_front_matter(src: str):
    m = re.match(r"^---\n(.*?)\n---\n", src, re.S)
    if not m:
        return {}, src
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, src[m.end():]


def convert_alerts(md: str) -> str:
    """GitHub `> [!TIP]` blockquotes -> <div class="alert tip">."""
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        m = re.match(r"^> \[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", lines[i])
        if not m:
            out.append(lines[i]); i += 1; continue
        kind = m.group(1).lower()
        body = []
        i += 1
        while i < len(lines) and lines[i].startswith(">"):
            body.append(re.sub(r"^> ?", "", lines[i])); i += 1
        out.append(f'<div class="alert {kind}" markdown="1">')
        out.append(f'<p class="alert-title">{m.group(1).title()}</p>')
        out.extend(body)
        out.append("</div>")
    return "\n".join(out)


def extract_faq(md: str):
    faq = []
    sec = md.split("## 常见问题 FAQ", 1)
    if len(sec) < 2:
        return faq
    body = sec[1].split("\n## ", 1)[0]
    for q, a in re.findall(r"### Q：(.+?)\n+(.+?)(?=\n### |\Z)", body, re.S):
        a = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a)
        a = re.sub(r"[*`]", "", a).strip()
        faq.append({"@type": "Question", "name": q.strip(),
                    "acceptedAnswer": {"@type": "Answer", "text": a}})
    return faq


def render_markdown(body_md: str, depth: int) -> str:
    # GitHub starts a list right after a paragraph line; python-markdown needs a blank line.
    body_md = re.sub(r"(?m)^(?![\s>*\-]|\d+\.)(.+)\n(?=(?:[-*]|\d+\.) )", r"\1\n\n", body_md)
    md = markdown.Markdown(extensions=[
        "tables", "fenced_code", "md_in_html", "sane_lists",
        TocExtension(slugify=lambda v, s: github_slug(v), toc_depth="2-3"),
    ])
    out = md.convert(convert_alerts(body_md))
    # External links open in a new tab; our own links stay dofollow.
    out = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', out)
    # Links to the GitHub Pages site itself: make them relative so they work in any deploy.
    out = out.replace(f'href="{SITE_URL}"', 'href="' + ("../" * depth or "./") + '"')
    out = re.sub(r'href="' + re.escape(SITE_URL) + r'([a-z0-9-]+)/" target="_blank" rel="noopener"',
                 lambda m: 'href="' + ("../" * depth) + m.group(1) + '/"', out)
    out = re.sub(r'href="' + re.escape(SITE_URL) + r'" target="_blank" rel="noopener"',
                 'href="' + ("../" * depth or "./") + '"', out)
    # A bold line whose link starts with 👉 is a call to action -> button.
    out = re.sub(r'<p><strong>👉 ?<a ([^>]*)>(.*?)</a></strong>(.*?)</p>',
                 r'<p class="cta-wrap"><a class="cta" \1>\2 →</a>\3</p>', out, flags=re.S)
    out = re.sub(r'<strong>👉 ?<a ([^>]*)>(.*?)</a></strong>',
                 r'<a class="cta" \1>\2 →</a>', out, flags=re.S)
    out = out.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    out = re.sub(r'<img ', '<img loading="lazy" decoding="async" ', out)
    if depth:
        out = out.replace('src="images/', 'src="' + "../" * depth + 'images/')
    return out


# ---------- build ----------

def build_page(meta, body_md, all_pages, tpl):
    depth = 1 if meta["slug"] else 0
    url = SITE_URL + (meta["slug"] + "/" if meta["slug"] else "")
    rel_root = "../" * depth or "./"

    h1 = re.search(r"^# (.+)$", body_md, re.M).group(1).strip()
    body_md = re.sub(r"^\s*# .+\n", "", body_md, count=1)
    upd = re.search(r"最后更新：(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日", body_md)
    modified = date(*map(int, upd.groups())).isoformat() if upd else date.today().isoformat()

    content = render_markdown(body_md, depth)

    nav = "".join(
        f'<a href="{rel_root}{p["slug"] + "/" if p["slug"] else ""}"'
        + (' aria-current="page"' if p["slug"] == meta["slug"] else "")
        + f'>{html.escape(p["nav"])}</a>'
        for p in all_pages)

    ld = [{
        "@context": "https://schema.org", "@type": "Article",
        "headline": h1, "description": meta["description"], "inLanguage": "zh-CN",
        "image": OG_IMAGE, "datePublished": PUBLISHED, "dateModified": modified,
        "author": {"@type": "Person", "name": "dsom-w", "url": "https://github.com/dsom-w"},
        "mainEntityOfPage": url,
    }]
    faq = extract_faq(body_md)
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq})
    if depth:
        ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": HOME["nav"], "item": SITE_URL},
            {"@type": "ListItem", "position": 2, "name": meta["nav"], "item": url}]})

    page = tpl
    for k, v in {
        "TITLE": html.escape(meta["title"]), "H1": html.escape(h1),
        "DESCRIPTION": html.escape(meta["description"]), "KEYWORDS": html.escape(meta["keywords"]),
        "URL": url, "SITE_URL": SITE_URL, "REPO_URL": REPO_URL, "OG_IMAGE": OG_IMAGE,
        "MODIFIED": modified, "NAV": nav, "CTA": html.escape(meta["cta"]), "CTA_URL": meta["cta_url"],
        "JSONLD": json.dumps(ld, ensure_ascii=False, indent=1), "CONTENT": content,
        "ROOT": rel_root,
    }.items():
        page = page.replace("{{" + k + "}}", v)

    out_dir = meta["slug"] or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    return {"url": url, "modified": modified, "h1": h1, "faq": len(faq), **meta}


def main():
    tpl = open("template.html", encoding="utf-8").read()
    pages = []  # (meta, body)
    pages.append((HOME, open("README.md", encoding="utf-8").read()))
    for path in sorted(glob.glob("pages/*.md")):
        meta, body = parse_front_matter(open(path, encoding="utf-8").read())
        for k in ("slug", "title", "nav", "description", "keywords", "cta", "cta_url"):
            assert meta.get(k), f"{path}: missing front matter `{k}`"
        pages.append((meta, body))
    metas = [m for m, _ in pages]

    built = [build_page(m, b, metas, tpl) for m, b in pages]

    with open("sitemap.xml", "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for i, b in enumerate(built):
            f.write(f'  <url><loc>{b["url"]}</loc><lastmod>{b["modified"]}</lastmod>'
                    f'<changefreq>weekly</changefreq><priority>{"1.0" if i == 0 else "0.8"}</priority></url>\n')
        f.write('</urlset>\n')
    with open("robots.txt", "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
    with open("llms.txt", "w", encoding="utf-8") as f:
        f.write(f"# {HOME['nav']}\n\n> {HOME['description']}\n\n## 页面\n\n")
        for b in built:
            f.write(f"- [{b['h1']}]({b['url']}): {b['description']}\n")
        f.write(f"\n## 来源\n\n- 仓库：{REPO_URL}\n- 内容许可：CC BY-NC-SA 4.0\n")

    for b in built:
        print(f"{b['url']:<60} FAQ={b['faq']} lastmod={b['modified']}")


if __name__ == "__main__":
    main()
