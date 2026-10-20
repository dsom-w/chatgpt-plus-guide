#!/usr/bin/env python3
"""Build index.html (GitHub Pages) from README.md.

Run `python3 build.py` after editing README.md, then commit both files.
Requires: pip install markdown
"""
import html
import json
import re
import unicodedata
from datetime import date

import markdown
from markdown.extensions.toc import TocExtension

SITE_URL = "https://dsom-w.github.io/chatgpt-plus-guide/"
REPO_URL = "https://github.com/dsom-w/chatgpt-plus-guide"
OG_IMAGE = SITE_URL + "images/chatgpt/1-1-plans.webp"
TITLE = "ChatGPT Plus 国内开通指南（2026）：支付宝 / 微信 3 分钟自助充值，附海外卡、礼品卡、代充对比"
DESCRIPTION = (
    "2026 年国内开通 ChatGPT Plus / Pro 和 Claude Pro 的四条路线对比："
    "海外卡、虚拟信用卡、美区 Apple 礼品卡、代充，逐条讲真实成本与风险；"
    "附支付宝 / 微信自助充值全流程实测截图，不要密码、不换号、安卓 iPhone 都能用。"
)
KEYWORDS = (
    "ChatGPT Plus 国内开通, ChatGPT Plus 支付宝, ChatGPT Plus 微信支付, ChatGPT 代充, "
    "ChatGPT Plus 充值, Claude Pro 国内开通, Claude Pro 代充, ChatGPT Pro 国内, "
    "美区礼品卡 ChatGPT, 虚拟信用卡 ChatGPT, OpenAI 支付失败, your card was declined"
)


def github_slug(text: str) -> str:
    """Mimic GitHub's heading anchor algorithm so README links keep working."""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return text.replace(" ", "-")


def convert_alerts(md: str) -> str:
    """Turn GitHub `> [!TIP]` blockquotes into <div class="alert tip">."""
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
    """Collect '### Q：...' + following paragraph pairs for FAQPage JSON-LD."""
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


def main():
    src = open("README.md", encoding="utf-8").read()
    # Drop the H1: the template renders it from TITLE.
    body_md = re.sub(r"^# .+\n", "", src, count=1)
    updated = re.search(r"最后更新：(\d{4}) 年 (\d{1,2}) 月 (\d{1,2}) 日", src)
    modified = (date(*map(int, updated.groups())).isoformat() if updated else date.today().isoformat())

    md = markdown.Markdown(extensions=[
        "tables", "fenced_code", "md_in_html", "sane_lists",
        TocExtension(slugify=lambda v, s: github_slug(v), toc_depth="2-3"),
    ])
    # GitHub starts a list right after a paragraph line; python-markdown needs a blank line.
    body_md = re.sub(r"(?m)^(?![\s>*\-]|\d+\.)(.+)\n(?=(?:[-*]|\d+\.) )", r"\1\n\n", body_md)
    content = md.convert(convert_alerts(body_md))
    # External links: open in new tab (GitHub Pages lets us keep follow links).
    content = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', content)
    content = content.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    content = re.sub(r'<img ', '<img loading="lazy" decoding="async" ', content)

    ld = [
        {"@context": "https://schema.org", "@type": "Article",
         "headline": TITLE, "description": DESCRIPTION, "inLanguage": "zh-CN",
         "image": OG_IMAGE, "datePublished": "2026-10-20", "dateModified": modified,
         "author": {"@type": "Person", "name": "dsom-w", "url": "https://github.com/dsom-w"},
         "mainEntityOfPage": SITE_URL},
    ]
    faq = extract_faq(src)
    if faq:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq})

    tpl = open("template.html", encoding="utf-8").read()
    page = (tpl.replace("{{TITLE}}", html.escape(TITLE))
               .replace("{{DESCRIPTION}}", html.escape(DESCRIPTION))
               .replace("{{KEYWORDS}}", html.escape(KEYWORDS))
               .replace("{{SITE_URL}}", SITE_URL)
               .replace("{{REPO_URL}}", REPO_URL)
               .replace("{{OG_IMAGE}}", OG_IMAGE)
               .replace("{{MODIFIED}}", modified)
               .replace("{{JSONLD}}", json.dumps(ld, ensure_ascii=False, indent=1))
               .replace("{{CONTENT}}", content))
    open("index.html", "w", encoding="utf-8").write(page)

    open("sitemap.xml", "w", encoding="utf-8").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}</loc><lastmod>{modified}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
        '</urlset>\n')
    open("robots.txt", "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
    print(f"index.html written ({len(page):,} bytes), FAQ entries: {len(faq)}, lastmod {modified}")


if __name__ == "__main__":
    main()
