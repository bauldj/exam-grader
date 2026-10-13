# -*- coding: utf-8 -*-
"""
批改标记落点程序化验证：扫描批改图中的红色像素，按 y 聚类，
与 marks.json 中的期望坐标比对，偏差超容差即报警。

用法：
  python verify_marks.py --graded 批改图.jpg --config marks.json [--tol 30]

原理：手绘红笔标记颜色为 R>140 且 G<110 且 B<110。
按 x 区间分离左右栏（col L/R 的标记 x 各不相同，取标记 x ± 90 范围）。
目测缩略图会误判位置（0.5倍缩放下偏差数十像素），必须程序化验证。
"""
import argparse
import json

import numpy as np
from PIL import Image


def red_clusters(im, x1, x2, gap=40):
    """返回指定 x 区间内红色像素的 y 聚类中心列表"""
    a = np.array(im.convert("RGB")).astype(int)
    zone = a[:, x1:x2]
    red = (zone[:, :, 0] > 140) & (zone[:, :, 1] < 110) & (zone[:, :, 2] < 110)
    ys = np.where(red.any(axis=1))[0]
    groups, centers = [], []
    if len(ys):
        start = prev = ys[0]
        for y in ys[1:]:
            if y - prev > gap:
                groups.append((start, prev))
                start = y
            prev = y
        groups.append((start, prev))
        centers = [(a + b) // 2 for a, b in groups]
    return centers


def main():
    ap = argparse.ArgumentParser(description="批改标记落点验证")
    ap.add_argument("--graded", required=True, help="批改后的终版图")
    ap.add_argument("--config", required=True, help="marks.json")
    ap.add_argument("--tol", type=int, default=35, help="容差(px)，默认35")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fp:
        cfg = json.load(fp)
    a = np.array(Image.open(args.graded).convert("RGB")).astype(int)
    red = (a[:, :, 0] > 140) & (a[:, :, 1] < 110) & (a[:, :, 2] < 110)

    # 注意：得分/批语文字也是红色，会与符号聚成同一簇或在下方形成相邻簇，
    # 因此不用"聚类中心=期望位置"匹配，而是验证每个期望位置邻域内是否有红色笔画。
    problems, ok_count = [], 0
    for m in cfg.get("marks", []):
        mx, my = m["x"], m["y"]
        y1, y2 = max(0, my - args.tol), my + args.tol
        x1, x2 = max(0, mx - 90), min(a.shape[1], mx + 90)
        rows = int(red[y1:y2, x1:x2].any(axis=1).sum())
        if rows >= 3:
            ok_count += 1
        else:
            problems.append(f"  第{m['no']}题: 期望 y={my} 附近未见红色笔迹(仅{rows}行), 标记可能缺失或错位")

    n_expected = len(cfg.get("marks", []))
    print(f"期望 {n_expected} 个标记, 命中 {ok_count} 个")
    if problems:
        print("发现问题:")
        print("\n".join(problems))
        raise SystemExit(1)
    print("✅ 全部标记落点验证通过")


if __name__ == "__main__":
    main()
