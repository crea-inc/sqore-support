#!/usr/bin/env python3
"""ストアのバッジの右に、パソコンで見ている人向けの QR を入れる(何度流しても同じ結果)。

全ページの <div class="store-btns">…</div> の中の最後に <img class="qr-get"> を1つ入れる(バッジと同じ並び・説明文なし)。
QR の中身は https://sqore-golf.com/get/(スマホで開くと App Store / Google Play へ飛ぶ中継ページ)。
出すのはパソコンだけ。見た目は assets/footer.css の .qr-get にある(既定は非表示)。
既に入っている所は触らない。get/ と r/ には入れない。

新しいページを足したら `python3 tools/qr_block.py` を流す。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {"get", "r"}  # 中継ページ・受け口には入れない

BTNS_RE = re.compile(r"^([ \t]*)<div class=\"store-btns\">.*?\n\1</div>\n", re.S | re.M)
OLD_RE = re.compile(r"^[ \t]*<div class=\"qr-get\">.*?</div>\n", re.S | re.M)  # 11/15 の最初の形(文つきの箱)を外す
IMG = '{i}  <img class="qr-get" src="{p}assets/qr_get.svg" alt="スマホで読み取るQRコード" width="74" height="74" loading="lazy" decoding="async">\n'


def fix(path):
    rel = path.relative_to(ROOT)
    if rel.parts[0] in SKIP:
        return False
    text = path.read_text(encoding="utf-8")
    prefix = "../" * (len(rel.parts) - 1)

    def add(m):
        block = m.group(0)
        if 'class="qr-get"' in block:
            return block
        i = m.group(1)
        tail = i + "</div>\n"
        return block[: -len(tail)] + IMG.format(i=i, p=prefix) + tail

    new = BTNS_RE.sub(add, OLD_RE.sub("", text))
    if new != text:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    changed = [p for p in sorted(ROOT.rglob("*.html")) if ".git" not in p.parts and fix(p)]
    for p in changed:
        print(p.relative_to(ROOT))
    print(f"{len(changed)} files")


if __name__ == "__main__":
    main()
