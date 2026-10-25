#!/usr/bin/env python3
"""お知らせページ news/index.html を news/news.json から作る。

news.json はアプリ(iOS・Android)も読みに来る。中身はここだけで書き、ページは手で直さない。
  items: 新しい順。各項目は
    id     : 一意の文字列(アプリの既読の印。出した後は変えない)
    date   : "yyyy-mm-dd"
    title  : 見出し(アプリのホームの帯にもこのまま出る。短く)
    body   : 本文。改行で段落を分ける
    banner : true ならアプリのホームに帯で1回出す(見る・×で既読)。サイトのトップにも帯で出す
    until  : 任意 "yyyy-mm-dd"。この日を過ぎたら帯を出さない(一覧には残る)。
             サイトのトップは書き出した時点で判定するので、期限を過ぎたら一度走らせ直す
    url    : 任意。くわしいページへのリンク
    below_ios / below_android : 任意 "2.6.5" の形。その版より古いアプリにだけ出す(更新のお願い用)。
             アプリ 2.6.3 / 1.3.3 から効く。それより前の版は無視して全員に出すので注意。
             サイトのお知らせページには出すが、トップの帯には出さない

使い方: python3 tools/mknews.py
"""
import datetime
import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "news", "news.json")
OUT = os.path.join(ROOT, "news", "index.html")
TOP = os.path.join(ROOT, "index.html")
TOPNEWS = re.compile(r"<!--TOPNEWS-->.*?<!--/TOPNEWS-->", re.S)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def load():
    with open(SRC, encoding="utf-8") as f:
        items = json.load(f)["items"]
    ids = set()
    for it in items:
        for k in ("id", "date", "title", "body"):
            assert isinstance(it.get(k), str) and it[k].strip(), f"{k} がない: {it}"
        assert DATE.match(it["date"]), f"date の形: {it['date']}"
        if "until" in it:
            assert DATE.match(it["until"]), f"until の形: {it['until']}"
        for k in ("below_ios", "below_android"):
            if k in it:
                assert re.match(r"^\d+(\.\d+)*$", str(it[k])), f"{k} の形: {it[k]}"
        assert it["id"] not in ids, f"id の重複: {it['id']}"
        ids.add(it["id"])
    return items


def jp_date(s):
    d = datetime.date.fromisoformat(s)
    return f"{d.year}年{d.month}月{d.day}日"


def render(items):
    e = html.escape
    arts = []
    for it in items:
        paras = "\n".join(f"<p>{e(p)}</p>" for p in it["body"].split("\n") if p.strip())
        link = f'\n<p><a href="{e(it["url"])}">くわしくはこちら</a></p>' if it.get("url") else ""
        arts.append(
            f'<article class="news" id="{e(it["id"])}">\n'
            f'<time datetime="{e(it["date"])}">{jp_date(it["date"])}</time>\n'
            f'<h2>{e(it["title"])}</h2>\n{paras}{link}\n</article>')
    body = "\n\n".join(arts) if arts else "<p>いまお知らせはありません。</p>"
    tpl = open(os.path.join(ROOT, "tools", "news_template.tmpl"), encoding="utf-8").read()
    return tpl.replace("<!--NEWS-->", body)


def top_banner(items, today):
    """トップの帯: アプリの帯と同じ選び方(帯の印あり・期限内のうち一番新しいもの。同じ日なら上)。無ければ空。"""
    open_ = [it for it in items if it.get("banner") and it.get("until", "9999-12-31") >= today
             and "below_ios" not in it and "below_android" not in it]
    if not open_:
        return ""
    newest = max(it["date"] for it in open_)
    it = next(it for it in open_ if it["date"] == newest)
    e = html.escape
    return (f'<a class="top-news" href="news/#{e(it["id"])}">'
            f'<span class="top-news-label">お知らせ</span>'
            f'<time datetime="{e(it["date"])}">{jp_date(it["date"])}</time>'
            f'<span class="top-news-title">{e(it["title"])}</span>'
            f'<span class="top-news-arrow" aria-hidden="true">›</span></a>')


if __name__ == "__main__":
    items = load()
    out = render(items)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", os.path.relpath(OUT, ROOT))
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
    top = open(TOP, encoding="utf-8").read()
    assert len(TOPNEWS.findall(top)) == 1, "index.html に <!--TOPNEWS--><!--/TOPNEWS--> が無い"
    top = TOPNEWS.sub(lambda m: "<!--TOPNEWS-->" + top_banner(items, today) + "<!--/TOPNEWS-->", top)
    with open(TOP, "w", encoding="utf-8") as f:
        f.write(top)
    print("wrote index.html")
