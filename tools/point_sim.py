#!/usr/bin/env python3
"""rules/point.html の数値を出すシミュレーション。

精算はSQOREアプリ(NigiriEngine.pointGameHole)と同じ:
  1ホールの各自の点 = 役の点(イーグル以上/バーディ/パー/ボギー/ダボ/トリ以上/ダブルパー)
                    + ニアピン点 × (持ち越し込みの本数)
  そのホールの収支 = 人数 × 自分の点 − 全員の点の合計   (= 相手1人ずつとの差の合計)
  役の判定順: ダブルパー以上 → イーグル以上 → バーディ → パー → ボギー → ダボ → トリ以上

1ホールの打数 = パー + (腕前ごとの離散分布から引いた「パーからの打数」)。各ホール独立。
正規分布の形(handicap_sim.py)だとバーディとイーグルが現実より多く出すぎたため、
アマチュアのおおよその出現率(下の DIST)を直接置いた。トリ以上は 3 + 幾何分布の上乗せ。
ニアピン: PAR3で1打目が乗る確率を腕前ごとに置き、乗った人から1人を無作為に勝者にする。
誰も乗らなければ次のPAR3へ持ち越す。打数とは独立に決めている(簡略化)。

使い方:  python3 tools/point_sim.py
必要: Python 3.9+ と numpy
"""
from __future__ import annotations

import numpy as np

SEED = 20261103
TRIALS = 100_000
PARS = np.array([4, 4, 3, 5, 4, 4, 3, 4, 5,
                 4, 3, 4, 5, 4, 4, 3, 5, 4])
# 平均グロス: (イーグル, バーディ, パー, ボギー, ダボ, トリ以上), トリ以上の平均(パーから)
DIST = {
    80: ((0.001, 0.09, 0.47, 0.339, 0.08, 0.02), 3.4),
    90: ((0.0005, 0.04, 0.29, 0.40, 0.19, 0.0795), 3.4),
    100: ((0.0002, 0.015, 0.15, 0.37, 0.28, 0.1848), 3.5),
    110: ((0.0001, 0.005, 0.07, 0.29, 0.32, 0.3149), 3.7),
}
# PAR3で1打目がグリーンに乗る確率(平均グロス別のおおよその目安)
ON_P3 = {80: 0.40, 90: 0.25, 100: 0.15, 110: 0.08}

DEFAULT = dict(eagle=50, birdie=10, par=0, bogey=0, double=0, triple=0, dpar=0, nearpin=10)
MINUS = dict(eagle=50, birdie=10, par=5, bogey=0, double=-5, triple=-10, dpar=-10, nearpin=10)


def gen(rng, level, trials):
    """(trials, 18) の打数。"""
    probs, tri_mean = DIST[level]
    k = rng.choice(6, size=(trials, 18), p=np.array(probs) / sum(probs))
    over = np.array([-2, -1, 0, 1, 2, 3])[k]
    extra = rng.geometric(1 / (1 + (tri_mean - 3)), size=(trials, 18)) - 1
    over = np.where(k == 5, 3 + extra, over)
    return PARS + over


def role(s, par, cfg):
    return np.select(
        [s >= par * 2, s <= par - 2, s == par - 1, s == par, s == par + 1, s == par + 2],
        [cfg["dpar"], cfg["eagle"], cfg["birdie"], cfg["par"], cfg["bogey"], cfg["double"]],
        cfg["triple"])


def run(levels, cfg, carry=True, seed=SEED):
    rng = np.random.default_rng(seed)
    n = len(levels)
    S = np.stack([gen(rng, g, TRIALS) for g in levels], axis=1)  # (T, n, 18)
    raw = role(S, PARS, cfg).astype(np.int64)
    # ニアピン
    pool = np.ones(TRIALS, dtype=np.int64)
    for h in np.where(PARS == 3)[0]:
        on = np.stack([rng.random(TRIALS) < ON_P3[g] for g in levels], axis=1)
        anyon = on.any(axis=1)
        pick = rng.random((TRIALS, n)) * on
        win = pick.argmax(axis=1)
        add = np.zeros((TRIALS, n), dtype=np.int64)
        add[np.arange(TRIALS)[anyon], win[anyon]] = cfg["nearpin"] * pool[anyon]
        raw[:, :, h] += add
        pool = np.where(anyon, 1, pool + 1 if carry else 1)
    net = n * raw - raw.sum(axis=1, keepdims=True)  # (T, n, 18)
    total = net.sum(axis=2)  # (T, n)
    return S, total


def report(title, levels, cfg):
    S, total = run(levels, cfg)
    print(f"## {title}  levels={levels}")
    print("  平均グロス:", np.round(S.sum(axis=2).mean(axis=0), 1))
    print("  1人の平均収支pt:", np.round(total.mean(axis=0), 1))
    print("  収支の絶対値の平均pt(1人):", round(float(np.abs(total).mean()), 1))
    print("  勝ち越す確率:", np.round((total > 0).mean(axis=0), 3))
    print("  トップの平均pt:", round(float(total.max(axis=1).mean()), 1))
    print("  最大の負け(1%点):", int(np.percentile(total.min(axis=1), 1)))
    print()


def main():
    even = [90, 90, 90, 90]
    mixed = [80, 90, 100, 110]
    report("既定・互角", even, DEFAULT)
    report("既定・実力差", mixed, DEFAULT)
    report("減点あり・互角", even, MINUS)
    report("減点あり・実力差", mixed, MINUS)
    # 役の出現回数(1人18ホールあたり)
    rng = np.random.default_rng(SEED)
    for g in mixed:
        s = gen(rng, g, TRIALS)
        d = s - PARS
        print(g, "eagle", round(float((d <= -2).sum(1).mean()), 2),
              "birdie", round(float((d == -1).sum(1).mean()), 2),
              "par", round(float((d == 0).sum(1).mean()), 2),
              "double+", round(float((d >= 2).sum(1).mean()), 2))


if __name__ == "__main__":
    main()
