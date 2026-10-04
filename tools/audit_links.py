#!/usr/bin/env python3
"""sqore-golf.com の内部リンク棚卸し。

リポジトリ内の .html を全部読み、ページごとに次を表で出す:
  - in   : 被リンク数（他ページからの <a href> の本数。ナビ・パンくず・フッター込み。自己リンクは除く）
  - pages: 被リンク元のページ数
  - depth: トップ（/）からのクリック数（幅優先探索。到達できなければ "-"）
  - desc : meta description の文字数（86〜120 字の外は "!"）
  - h1 / canonical / og:image / JSON-LD の数と、JSON-LD がパースできるか

使い方:
  python3 tools/audit_links.py            # 全ページの表
  python3 tools/audit_links.py --check    # 問題のある行だけ（終了コード 1）
  python3 tools/audit_links.py course/search/   # 指定ページの被リンク元を列挙

リダイレクト用のスタブ（meta refresh だけのページ）と 404.html は判定から外す。
"""
import json
import os
import re
import sys
from collections import defaultdict, deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://sqore-golf.com/"
DESC_MIN, DESC_MAX = 86, 120
INBOUND_MIN = 5
DEPTH_MAX = 2


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.h1 = 0
        self.canonical = []
        self.og_image = 0
        self.desc = None
        self.refresh = False
        self.ld_blocks = []
        self._in_ld = False
        self._ld_buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "h1":
            self.h1 += 1
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href", ""))
        elif tag == "meta":
            if a.get("property") == "og:image":
                self.og_image += 1
            if a.get("name") == "description":
                self.desc = a.get("content", "")
            if (a.get("http-equiv") or "").lower() == "refresh":
                self.refresh = True
        elif tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []

    def handle_endtag(self, tag):
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.ld_blocks.append("".join(self._ld_buf))

    def handle_data(self, data):
        if self._in_ld:
            self._ld_buf.append(data)


def page_url(rel):
    """ファイルパス → サイト上のパス（/ 始まり。index.html はディレクトリ）"""
    p = "/" + rel.replace(os.sep, "/")
    if p.endswith("/index.html"):
        p = p[: -len("index.html")]
    return p


def normalize(href, base):
    if href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    full = urljoin(SITE.rstrip("/") + base, href)
    u = urlparse(full)
    if u.netloc and u.netloc != "sqore-golf.com":
        return None
    path = u.path or "/"
    if path.endswith("/index.html"):
        path = path[: -len("index.html")]
    return path


def ld_types(blocks):
    types, ok = [], True
    for b in blocks:
        try:
            data = json.loads(b)
        except Exception:
            ok = False
            continue
        items = data if isinstance(data, list) else [data]
        for it in items:
            t = it.get("@type")
            types.extend(t if isinstance(t, list) else [t])
    return types, ok


def collect():
    pages = {}
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in fn:
            if not f.endswith(".html"):
                continue
            rel = os.path.relpath(os.path.join(dp, f), ROOT)
            with open(os.path.join(dp, f), encoding="utf-8") as fh:
                pp = PageParser()
                pp.feed(fh.read())
            pages[page_url(rel)] = (rel, pp)
    return pages


def main():
    pages = collect()
    inbound = defaultdict(int)
    sources = defaultdict(set)
    graph = defaultdict(set)
    broken = []
    for url, (rel, pp) in pages.items():
        for href in pp.links:
            tgt = normalize(href, url)
            if tgt is None:
                continue
            if tgt not in pages:
                if not re.search(r"\.(png|webp|svg|jpg|mp4|txt|xml|pdf)$", tgt):
                    broken.append((url, href))
                continue
            if tgt == url:
                continue
            inbound[tgt] += 1
            sources[tgt].add(url)
            graph[url].add(tgt)

    depth = {"/": 0}
    q = deque(["/"])
    while q:
        u = q.popleft()
        for v in graph[u]:
            if v not in depth:
                depth[v] = depth[u] + 1
                q.append(v)

    if len(sys.argv) > 1 and sys.argv[1] != "--check":
        tgt = normalize(sys.argv[1], "/")
        print(f"{tgt}: 被リンク {inbound[tgt]} 本 / {len(sources[tgt])} ページ / トップから {depth.get(tgt, '-')} クリック")
        for s in sorted(sources[tgt]):
            n = sum(1 for h in pages[s][1].links if normalize(h, s) == tgt)
            print(f"  {s}  ×{n}")
        return 0

    check = "--check" in sys.argv
    rows, bad = [], 0
    for url in sorted(pages, key=lambda u: (u.count("/"), u)):
        rel, pp = pages[url]
        if pp.refresh or rel == "404.html":
            continue
        dlen = len(pp.desc) if pp.desc is not None else 0
        types, ld_ok = ld_types(pp.ld_blocks)
        d = depth.get(url)
        problems = []
        if inbound[url] < INBOUND_MIN and url != "/":
            problems.append(f"被リンク{inbound[url]}")
        if d is None or d > DEPTH_MAX:
            problems.append(f"深さ{d if d is not None else '到達不能'}")
        if not (DESC_MIN <= dlen <= DESC_MAX):
            problems.append(f"desc{dlen}字")
        if pp.h1 != 1:
            problems.append(f"h1×{pp.h1}")
        if len(pp.canonical) != 1:
            problems.append(f"canonical×{len(pp.canonical)}")
        if pp.og_image < 1:
            problems.append("og:imageなし")
        if not ld_ok:
            problems.append("JSON-LD壊れ")
        if not pp.ld_blocks:
            problems.append("JSON-LDなし")
        if problems:
            bad += 1
        if check and not problems:
            continue
        rows.append((url, inbound[url], len(sources[url]), "-" if d is None else d, dlen,
                     pp.h1, len(pp.canonical), pp.og_image, ",".join(t for t in types if t),
                     " ".join(problems)))

    print(f"{'page':42} {'in':>4} {'pages':>5} {'depth':>5} {'desc':>4} h1 can og  JSON-LD / 問題")
    for r in rows:
        print(f"{r[0]:42} {r[1]:>4} {r[2]:>5} {r[3]:>5} {r[4]:>4} {r[5]:>2} {r[6]:>3} {r[7]:>2}  {r[8]}" + (f"  ← {r[9]}" if r[9] else ""))
    if broken:
        print("\n切れているリンク:")
        for s, h in sorted(set(broken)):
            print(f"  {s} → {h}")
    print(f"\n{len(rows)} ページ表示 / 問題あり {bad} ページ / 切れリンク {len(set(broken))} 本")
    return 1 if (check and (bad or broken)) else 0


if __name__ == "__main__":
    sys.exit(main())
