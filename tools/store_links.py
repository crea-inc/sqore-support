#!/usr/bin/env python3
"""ストアへのリンクに、どのページから来たかの印を付ける(何度流しても同じ結果)。

Google Play: referrer=utm_source=sqore-golf&utm_medium=web&utm_campaign=<ページ>
  → Play Console の「ユーザー獲得」で UTM キャンペーン別のインストール数が見られる。
App Store: pt(提供元番号)が分かったら APP_STORE_PT に入れる。ct=<ページ> を付け、
  App Store Connect の「キャンペーン」で見られる。空のうちは App Store のリンクは触らない。

新しいページを足したら `python3 tools/store_links.py` を流す。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_STORE_PT = ""  # App Store Connect の「キャンペーンリンクを作成」に出る pt= の数字

PLAY = "https://play.google.com/store/apps/details?id=com.sqore.app"
PLAY_RE = re.compile(re.escape(PLAY) + r"(?:&amp;referrer=[^\"']*|&referrer=[^\"']*)?")
APPLE = "https://apps.apple.com/jp/app/id6777357472"
APPLE_RE = re.compile(re.escape(APPLE) + r"(?:\?pt=[^\"']*)?")


def campaign(path):
    rel = path.relative_to(ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "index":
        parts = parts[:-1]
    return "-".join(parts) or "top"


def fix(path):
    text = path.read_text(encoding="utf-8")
    c = campaign(path)
    play = PLAY + "&referrer=utm_source%3Dsqore-golf%26utm_medium%3Dweb%26utm_campaign%3D" + c
    out = []
    # JSON-LD(アプリの正式なURL)は印を付けない
    for i, chunk in enumerate(re.split(r"(<script type=\"application/ld\+json\">.*?</script>)", text, flags=re.S)):
        if i % 2:
            out.append(chunk)
            continue
        chunk = PLAY_RE.sub(play, chunk)
        if APP_STORE_PT:
            chunk = APPLE_RE.sub(APPLE + "?pt=" + APP_STORE_PT + "&ct=" + c + "&mt=8", chunk)
        out.append(chunk)
    new = "".join(out)
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    changed = [p for p in sorted(ROOT.rglob("*.html")) if ".git" not in p.parts and fix(p)]
    for p in changed:
        print(p.relative_to(ROOT), campaign(p))
    print(f"{len(changed)} files")


if __name__ == "__main__":
    main()
