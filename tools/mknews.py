#!/usr/bin/env python3
"""お知らせページ news/index.html を news/news.json から作る。

news.json はアプリ(iOS・Android)も読みに来る。中身はここだけで書き、ページは手で直さない。
  items: 新しい順。各項目は
    id     : 一意の文字列(アプリの既読の印。出した後は変えない)
    date   : "yyyy-mm-dd"
    title  : 見出し(アプリのホームの帯にもこのまま出る。短く)
    body   : 本文。改行で段落を分ける
    banner : true ならアプリのホームに帯で1回出す(見る・×で既読)
    until  : 任意 "yyyy-mm-dd"。この日を過ぎたら帯を出さない(一覧には残る)
    url    : 任意。くわしいページへのリンク

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


if __name__ == "__main__":
    out = render(load())
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)
    print("wrote", os.path.relpath(OUT, ROOT))
