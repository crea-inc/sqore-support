#!/usr/bin/env python3
"""score/handicap.html の数値を出すシミュレーション。

JGA『ハンディキャップ規則』（2024年1月施行）の式をそのまま実装して回す。
  スコアディファレンシャル = (113 / スロープ) x (調整グロス - CR - PCC)   小数第1位に四捨五入
  ハンディキャップインデックス(HI) = 直近20ラウンドの良い8つの平均（規則5.2b）
  ネットダブルボギー = パー + 2 + そのホールで受けるハンディキャップストローク
  ローハンディキャップインデックス = 直近365日で最も低かったHI（規則5.7）
  ソフトキャップ = ローHI + 3.0 を超える増加分を50%に（規則5.8）
  ハードキャップ = ローHI + 5.0 で頭打ち（規則5.8）

前提（記事の note と同じ）:
  - ホールごとのスコアを乱数で生成する。PCC調整値は0。
  - ネットダブルボギーのハンディキャップストロークはパーの大きいホールから順に配分。
  - コースは記事の5コース(A〜E, すべてパー72)からランダムに選ぶ。各条件4,000回。
  - 例外的スコアの減算(規則5.9)は入れていない。

1ホールのスコア = パー + max(-1, 四捨五入(平均オーバー + HOLE_SD×正規乱数 + 調子/18))。
調子はラウンドごとの正規乱数（FORM_SD 打）。8月の元スクリプトは残っていないので、
この2つの散らばりは記事の「4,000回の平均」表（平均グロス80〜105の6行）に合うよう選び直した。
最初に記事の数値（中央値7.0打と6行の表）を再現できるかを確かめ（reproduce）、
そのうえで同じ乱数列から新しい数字（scenario_a / b）を出す。

使い方:  python3 tools/handicap_sim.py          # 全部出す
         python3 tools/handicap_sim.py --svg    # 加えて検証④の折れ線SVGを標準出力へ
必要: Python 3.9+ と numpy
"""
from __future__ import annotations

import math
import sys

import numpy as np

SEED = 20261004
TRIALS = 4000
HOLE_SD = 1.3             # 1ホールのぶれ（打）
FORM_SD = 3.0             # ラウンドごとの調子のぶれ（18ホール合計で、打）

PARS = np.array([4, 4, 3, 5, 4, 4, 3, 4, 5,
                 4, 3, 4, 5, 4, 4, 3, 5, 4])
# パー3はやや少なく、パー5はやや多く叩く（1ホールあたりの平均オーバーの比）
PAR_WEIGHT = np.where(PARS == 3, 0.85, np.where(PARS == 5, 1.12, 1.0))
PAR_WEIGHT = PAR_WEIGHT / PAR_WEIGHT.mean()
# ストロークの配分順: パーの大きいホールから（同じパーは番号順）
STROKE_ORDER = sorted(range(18), key=lambda h: (-PARS[h], h))

COURSES = {  # 記事の5コース: (CR, スロープ)
    "A": (70.2, 118), "B": (71.4, 124), "C": (72.8, 131), "D": (69.6, 113), "E": (71.9, 127),
}
COURSE_KEYS = list(COURSES)

# 記事「20ラウンドで計算してみた」の表（コース, ディファレンシャル）。シナリオAの出発点。
ARTICLE_20 = [("B", 21.5), ("A", 22.8), ("C", 22.6), ("B", 17.9), ("D", 17.4),
              ("E", 23.2), ("A", 19.0), ("C", 19.1), ("B", 17.0), ("A", 13.2),
              ("E", 23.2), ("D", 28.4), ("B", 21.5), ("C", 16.6), ("A", 20.9),
              ("B", 22.4), ("E", 17.0), ("A", 18.0), ("C", 14.8), ("B", 21.5)]
ARTICLE_GROSS = [95, 97, 101, 93, 87, 99, 92, 96, 91, 86, 98, 102, 96, 93, 92, 96, 96, 91, 90, 103]

# 規則5.2a: 提出枚数 -> (採用枚数, 調整)
FEW = {3: (1, -2.0), 4: (1, -1.0), 5: (1, 0.0), 6: (2, -1.0), 7: (2, 0.0), 8: (2, 0.0),
       9: (3, 0.0), 10: (3, 0.0), 11: (3, 0.0), 12: (4, 0.0), 13: (4, 0.0), 14: (4, 0.0),
       15: (5, 0.0), 16: (5, 0.0), 17: (6, 0.0), 18: (6, 0.0), 19: (7, 0.0)}


def r1(x: float) -> float:
    """小数第1位へ四捨五入（0.05は外側へ）。"""
    return math.copysign(math.floor(abs(x) * 10 + 0.5 + 1e-9) / 10, x)


def hi_from(diffs: list[float]) -> float | None:
    n = len(diffs)
    if n < 3:
        return None
    if n >= 20:
        best = sorted(diffs[-20:])[:8]
        return min(54.0, r1(sum(best) / 8))
    k, adj = FEW[n]
    best = sorted(diffs)[:k]
    return min(54.0, r1(sum(best) / k + adj))


def course_hcp(hi: float, cr: float, slope: int) -> int:
    return int(math.floor(hi * slope / 113 + (cr - 72) + 0.5))


def adjusted(gross_holes: np.ndarray, hi: float | None, cr: float, slope: int) -> int:
    if hi is None:                     # HIが無いうちは パー+5 が上限（規則3.1b）
        caps = PARS + 5
    else:
        ch = course_hcp(hi, cr, slope)
        strokes = np.zeros(18, dtype=int)
        if ch > 0:
            base, extra = divmod(ch, 18)
            strokes += base
            for h in STROKE_ORDER[:extra]:
                strokes[h] += 1
        elif ch < 0:                   # プラスハンデはストロークを返す（逆順）
            for h in list(reversed(STROKE_ORDER))[:(-ch) % 18 or 0]:
                strokes[h] -= 1
        caps = PARS + 2 + strokes
    return int(np.minimum(gross_holes, caps).sum())


def differential(adj: int, cr: float, slope: int) -> float:
    return r1((113 / slope) * (adj - cr - 0.0))


def _phi(x: np.ndarray) -> np.ndarray:
    return 0.5 * (1 + np.vectorize(math.erf)(x / math.sqrt(2)))


def mean_over(mu: float) -> float:
    """平均オーバー mu のときの、18ホール合計の期待オーバー（-1の下限と四捨五入込み）。"""
    m = mu * PAR_WEIGHT
    sd = math.sqrt(HOLE_SD ** 2 + (FORM_SD / 18) ** 2)
    e = -_phi((-0.5 - m) / sd)
    for k in range(1, 15):
        e = e + k * (_phi((k + 0.5 - m) / sd) - _phi((k - 0.5 - m) / sd))
    return float(e.sum())


_MU_CACHE: dict[float, float] = {}


def mu_for(mean_gross: float) -> float:
    """平均グロスが mean_gross になる1ホールの平均オーバーを二分法で求める。"""
    if mean_gross not in _MU_CACHE:
        lo, hi = -1.0, 6.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if mean_over(mid) < mean_gross - 72:
                lo = mid
            else:
                hi = mid
        _MU_CACHE[mean_gross] = (lo + hi) / 2
    return _MU_CACHE[mean_gross]


class Stream:
    """全条件で共通に使う乱数列。trial ごとに ラウンドの調子・コース・ホールの正規乱数を固定で持つ。"""

    def __init__(self, trials: int, rounds: int, seed: int = SEED):
        rng = np.random.default_rng(seed)
        self.form = rng.standard_normal(size=(trials, rounds))
        self.course = rng.integers(0, len(COURSE_KEYS), size=(trials, rounds))
        self.z = rng.standard_normal(size=(trials, rounds, 18))

    def holes(self, t: int, r: int, mean_gross: float) -> np.ndarray:
        x = mu_for(mean_gross) * PAR_WEIGHT + HOLE_SD * self.z[t, r] + FORM_SD * self.form[t, r] / 18
        return PARS + np.maximum(-1, np.floor(x + 0.5)).astype(int)


def play(stream: Stream, t: int, rounds: range, mean_gross: float,
         diffs: list[float], his: list[float | None], gross: list[int],
         low_window: int | None = None, low_start: float | None = None, capped: list | None = None):
    """rounds の範囲を順に回し、ディファレンシャルとHIを積む。

    low_window を渡すとキャップ付きで回す（capped に (raw, soft, final, low) を積む）。
    ネットダブルボギーには、そのラウンド前の「実際に使われているHI」を使う。
    """
    for r in rounds:
        ck = COURSE_KEYS[stream.course[t, r]]
        cr, sl = COURSES[ck]
        h = stream.holes(t, r, mean_gross)
        adj = adjusted(h, his[-1] if his else None, cr, sl)
        gross.append(int(h.sum()))
        diffs.append(differential(adj, cr, sl))
        raw = hi_from(diffs)
        if low_window is None or raw is None:
            his.append(raw)
            continue
        recent = [x for x in his[-low_window:] if x is not None]
        low = min(recent + ([low_start] if low_start is not None else []))
        soft, final = caps(raw, low)
        capped.append((raw, soft, final, low))
        his.append(final)


def caps(raw: float, low: float) -> tuple[float, float]:
    inc = raw - low
    soft = raw if inc <= 3.0 else r1(low + 3.0 + (inc - 3.0) * 0.5)
    final = min(soft, r1(low + 5.0))
    return soft, final


# ---------------------------------------------------------------- 再現チェック

def reproduce(stream: Stream):
    """記事の数値（4,000回平均の表と中央値7.0打）を同じ前提で出し直す。

    各試行: 20ラウンドの履歴（ネットダブルボギー用のHIを作るため）→ 続く20ラウンドで計測。
    """
    rows = []
    for target in (80, 85, 90, 95, 100, 105):
        g_all, hi_all, gap_all = [], [], []
        for t in range(TRIALS):
            diffs, his, gross = [], [], []
            play(stream, t, range(0, 40), target, diffs, his, gross)
            g = sum(gross[20:40]) / 20
            g_all.append(g)
            hi_all.append(his[-1])
            gap_all.append(g - 72 - his[-1])
        rows.append((target, np.mean(g_all), np.mean(hi_all), np.mean(gap_all), np.median(gap_all)))
    return rows


def article_20_check():
    diffs = [d for _, d in ARTICLE_20]
    return hi_from(diffs), sum(ARTICLE_GROSS) / 20


def median_gap_947(stream: Stream):
    gaps, sds = [], []
    for t in range(TRIALS):
        diffs, his, gross = [], [], []
        play(stream, t, range(0, 40), 94.7, diffs, his, gross)
        gaps.append(sum(gross[20:40]) / 20 - 72 - his[-1])
        sds.append(np.std(gross[20:40], ddof=1))
    return float(np.median(gaps)), float(np.mean(sds))


# ---------------------------------------------------------------- 検証④

def scenario_a(stream: Stream, shift: float = 6.0):
    """記事の20ラウンド（HI16.5＝ローHI）のあと、20ラウンド続けて平均+6打で回った場合。

    出発点の20ラウンドは記事の表そのもの（乱数なし）。続く20ラウンドを TRIALS 回引き、
    ラウンドごとの中央値と、キャップに初めて触れたラウンドの中央値を出す。
    """
    base = [d for _, d in ARTICLE_20]
    mean_gross = sum(ARTICLE_GROSS) / 20 + shift      # 94.7 + 6 = 100.7
    per_round = np.zeros((TRIALS, 20, 3))
    first_soft, first_hard, gross_mean = [], [], []
    for t in range(TRIALS):
        diffs, his, gross, capped = list(base), [16.5], [], []
        play(stream, t, range(40, 60), mean_gross, diffs, his, gross,
             low_window=20, low_start=16.5, capped=capped)
        gross_mean.append(sum(gross) / 20)
        fs = fh = None
        for i, (raw, soft, final, low) in enumerate(capped):
            per_round[t, i] = (raw, soft, final)
            if fs is None and raw - low > 3.0:
                fs = i + 1
            if fh is None and soft > r1(low + 5.0):
                fh = i + 1
        first_soft.append(fs)
        first_hard.append(fh)
    med = np.median(per_round, axis=0)
    soft_hit = [x for x in first_soft if x is not None]
    hard_hit = [x for x in first_hard if x is not None]
    return {
        "mean_gross": float(np.mean(gross_mean)),
        "median_by_round": med,
        "soft_rate": len(soft_hit) / TRIALS,
        "hard_rate": len(hard_hit) / TRIALS,
        "soft_first_median": float(np.median(soft_hit)) if soft_hit else None,
        "hard_first_median": float(np.median(hard_hit)) if hard_hit else None,
    }


def scenario_b(stream: Stream, mean_gross: float = 94.7, per_year: int = 20):
    """実力の変わらないプレーヤー（平均グロス94.7）を TRIALS 人。年20ラウンド。

    40ラウンドで履歴とローHIを作ったあと、次の1年（20ラウンド）でキャップに触れた割合。
    再現チェック・シナリオAと同じ乱数列（ラウンド0〜39は再現チェックと同一、40〜59はAと同一の乱数）。
    """
    soft_n = hard_n = 0
    cut = []                 # キャップに触れた人の、1年で最も大きく削られた量
    for t in range(TRIALS):
        diffs, his, gross = [], [], []
        play(stream, t, range(0, 40), mean_gross, diffs, his, gross)
        capped = []
        play(stream, t, range(40, 40 + per_year), mean_gross, diffs, his, gross,
             low_window=per_year, capped=capped)
        if any(raw - low > 3.0 for raw, _, _, low in capped):
            soft_n += 1
            cut.append(max(raw - final for raw, _, final, _ in capped))
        if any(soft > r1(low + 5.0) for _, soft, _, low in capped):
            hard_n += 1
    return soft_n / TRIALS, hard_n / TRIALS, float(np.median(cut)) if cut else 0.0


# ---------------------------------------------------------------- 図

def svg_lines(med: np.ndarray) -> str:
    W, H = 380, 290
    x0, x1, y0, y1 = 34, 368, 240, 82          # プロット領域（y0が下）
    vmin, vmax = 16.0, 22.0

    def X(i):
        return x0 + (x1 - x0) * i / 20

    def Y(v):
        return y0 - (y0 - y1) * (v - vmin) / (vmax - vmin)

    series = [  # (列, 色, 太さ, 破線, ラベル)
        (0, "#c0392b", 2, "6 4", "キャップなし"),
        # ソフトキャップのみの線は、中央値ではハードキャップに届かず実際の線と重なるので描かない
        (2, "#0b5cab", 3, None, "実際のインデックス（ソフト＋ハード）"),
    ]
    out = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="lht lhd" xmlns="http://www.w3.org/2000/svg">',
           '<title id="lht">平均+6打が20ラウンド続いたときのハンディキャップインデックス</title>',
           f'<desc id="lhd">ローハンディキャップインデックス16.5から、キャップなしでは{med[-1,0]:.1f}まで上がるが、ソフトキャップとハードキャップで{med[-1,2]:.1f}に止まる。4,000回の中央値。</desc>',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="{x0}" y="20" font-size="13" fill="#1c1c1e" font-weight="700">平均+6打が続いたときのインデックス</text>']
    for v in range(16, 23, 1):
        out.append(f'<line x1="{x0}" y1="{Y(v):.1f}" x2="{x1}" y2="{Y(v):.1f}" stroke="#eef0f3" stroke-width="1"/>')
        out.append(f'<text x="{x0-8}" y="{Y(v)+4:.1f}" text-anchor="end" font-size="11" fill="#8e8e93">{v}</text>')
    for lv, lab in ((19.5, "ソフトキャップ 19.5"), (21.5, "ハードキャップ 21.5")):
        out.append(f'<line x1="{x0}" y1="{Y(lv):.1f}" x2="{x1}" y2="{Y(lv):.1f}" stroke="#b8860b" stroke-width="1" stroke-dasharray="3 3"/>')
        out.append(f'<text x="{x0+4}" y="{Y(lv)-4:.1f}" font-size="11" fill="#b8860b">{lab}</text>')
    out.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#d8d8dd" stroke-width="1.5"/>')
    for i in (0, 5, 10, 15, 20):
        out.append(f'<text x="{X(i):.1f}" y="{y0+15}" text-anchor="middle" font-size="11" fill="#8e8e93">{i}</text>')
    for col, color, w, dash, _ in series:
        pts = [(X(0), Y(16.5))] + [(X(i + 1), Y(med[i, col])) for i in range(20)]
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="{w}"{da} stroke-linejoin="round"/>')
    ly = 38
    for col, color, w, dash, lab in series:
        da = f' stroke-dasharray="{dash}"' if dash else ""
        out.append(f'<line x1="{x0+2}" y1="{ly}" x2="{x0+30}" y2="{ly}" stroke="{color}" stroke-width="{w+0.5}"{da}/>')
        out.append(f'<text x="{x0+38}" y="{ly+4}" font-size="12" fill="{color}" font-weight="700">{lab}</text>')
        ly += 18  # 凡例は縦に積む（スマホ幅で重ならないように）
    out.append(f'<text x="{x1}" y="{H-12}" text-anchor="end" font-size="11" fill="#6e6e73">横軸＝平均+6打で回ったラウンド数（4,000回の中央値）</text>')
    out.append("</svg>")
    return "\n".join(out)


def main():
    stream = Stream(TRIALS, 60)

    hi, g = article_20_check()
    print(f"記事の20ラウンド: 平均グロス {g:.2f} / HI {hi} / 平均-72 {g-72:.1f} / ズレ {g-72-hi:.1f}")

    med, sd = median_gap_947(stream)
    print(f"[再現] 平均グロス94.7・20ラウンド×{TRIALS}回: ズレの中央値 {med:.2f}（記事 7.0） / 20ラウンドのグロスSD平均 {sd:.2f}")

    article = {80: (8.0, 2.4, 5.6), 85: (13.1, 6.9, 6.2), 90: (18.1, 11.4, 6.7),
               95: (23.2, 16.1, 7.2), 100: (28.0, 20.4, 7.6), 105: (33.2, 25.0, 8.2)}
    print("[再現] 平均グロス | 平均-72 | HI | ズレ  （記事）")
    worst = 0.0
    for target, gm, him, gap, gmed in reproduce(stream):
        a = article[target]
        worst = max(worst, abs(him - a[1]), abs(gap - a[2]))
        print(f"  {target:>3} | {gm-72:5.1f} | {him:5.1f} | {gap:4.1f}   （{a[0]} / {a[1]} / {a[2]}）")
    print(f"[再現] 記事との最大差 {worst:.2f}（±0.3以内なら一致とみなす）")

    a = scenario_a(stream)
    m = a["median_by_round"]
    print(f"[A] 21〜40ラウンド目の平均グロス {a['mean_gross']:.2f}")
    print("[A] ラウンド | キャップなし | ソフトのみ | ソフト＋ハード（中央値）")
    for i in range(20):
        print(f"  {i+1:>2} | {m[i,0]:5.1f} | {m[i,1]:5.1f} | {m[i,2]:5.1f}")
    print(f"[A] ソフトキャップに触れた割合 {a['soft_rate']:.1%}・初めて触れたラウンドの中央値 {a['soft_first_median']}")
    print(f"[A] ハードキャップに触れた割合 {a['hard_rate']:.1%}・初めて触れたラウンドの中央値 {a['hard_first_median']}")

    soft, hard, cut = scenario_b(stream)
    print(f"[B] 実力が変わらない{TRIALS}人×1年(20ラウンド): ソフトキャップに触れた {soft:.1%} / ハードキャップに触れた {hard:.1%}"
          f" / 触れた人が削られた量の中央値 {cut:.1f}")

    if "--svg" in sys.argv:
        print(svg_lines(m))


if __name__ == "__main__":
    main()
