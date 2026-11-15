#!/usr/bin/env python3
"""ストアのバッジの下に、パソコンで見ている人向けの QR の箱を入れる(何度流しても同じ結果)。

全ページの <div class="store-btns">…</div> の直後に <div class="qr-get"> を1つ入れる。
QR の中身は https://sqore-golf.com/get/(スマホで開くと App Store / Google Play へ飛ぶ中継ページ)。
箱を出すのはパソコンだけ。見た目は assets/footer.css の .qr-get にある(既定は非表示)。
既に箱が入っている所は触らない。get/ と r/ には入れない。

新しいページを足したら `python3 tools/qr_block.py` を流す。
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {"get", "r"}  # 中継ページ・受け口には入れない

BTNS_RE = re.compile(r"^([ \t]*)<div class=\"store-btns\">.*?</div>\n", re.S | re.M)
BOX = (
    '{i}<div class="qr-get">\n'
    '{i}  <img src="{p}assets/qr_get.svg" alt="SQOREを入手するQRコード" width="111" height="111" loading="lazy" decoding="async">\n'
    '{i}  <span>スマホで読み取ると入手できます</span>\n'
    '{i}</div>\n'
)


def fix(path):
    rel = path.relative_to(ROOT)
    if rel.parts[0] in SKIP:
        return False
    text = path.read_text(encoding="utf-8")
    prefix = "../" * (len(rel.parts) - 1)

    def add(m):
        rest = text[m.end():]
        if rest.lstrip(" \t").startswith('<div class="qr-get">'):
            return m.group(0)
        return m.group(0) + BOX.format(i=m.group(1), p=prefix)

    new = BTNS_RE.sub(add, text)
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
