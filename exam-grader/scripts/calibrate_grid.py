# -*- coding: utf-8 -*-
"""
坐标标定网格生成：给扫描件叠加带标注的坐标网格，用于题位定位模板的标定。

用法：
  python calibrate_grid.py --paper 空白卷.png --out grid.png
  python calibrate_grid.py --paper 空白卷.png --out grid.png --spacing 50 --crop 2400,4100 --side L
  python calibrate_grid.py --paper 学生卷.png --out check.png --spacing 200 --scale 0.5

参数：
  --paper    扫描件路径（空白卷或学生卷）
  --out      输出标定图路径
  --spacing  网格间距(px)，默认200；细标定时用50
  --crop     只处理局部区域 "y1,y2"（细标定长题时用）
  --side     标注在左侧还是两侧（L=仅左侧，默认两侧）
  --scale    输出缩放，默认1.0（标定看细节用1.0，整卷读数用0.5）

建议流程（详见 references/workflow-details.md）：
  1. 整卷 200px 网格 + scale 0.5 → 读出各题粗略区间
  2. 长题/带图题/多小问题区域 → 50px 细网格 + crop → 精确定位
  3. 抽1-2份学生卷复核（学生卷与空白卷可能局部偏移，必须逐卷核对）
"""
import argparse

from PIL import Image, ImageDraw, ImageFont


def load_font(sz):
    for p in ('C:/Windows/Fonts/msyhbd.ttc', 'C:/Windows/Fonts/simhei.ttf'):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description="坐标标定网格生成")
    ap.add_argument("--paper", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--spacing", type=int, default=200)
    ap.add_argument("--crop", default=None, help="y1,y2 只处理局部")
    ap.add_argument("--side", default="both", choices=["both", "L"])
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()

    im = Image.open(args.paper).convert("RGB")
    W, H = im.size
    y1, y2 = 0, H
    if args.crop:
        y1, y2 = [int(v) for v in args.crop.split(",")]

    ov = im.copy()
    d = ImageDraw.Draw(ov)
    f = load_font(max(20, args.spacing // 8))
    for y in range(y1 - y1 % args.spacing, y2 + 1, args.spacing):
        major = (y % (args.spacing * 2) == 0)
        d.line([(0, y), (W, y)], fill=(255, 0, 255), width=3 if major else 1)
        if major:
            d.text((6, y + 2), str(y), fill=(255, 0, 255), font=f)
            if args.side == "both":
                d.text((W - f.getlength(str(y)) - 8, y + 2), str(y), fill=(255, 0, 255), font=f)

    out = ov.crop((0, y1, W, y2))
    if args.scale != 1.0:
        out = out.resize((int(W * args.scale), int((y2 - y1) * args.scale)))
    out.save(args.out)
    print(f"OK {args.out} {out.size[0]}x{out.size[1]} (网格间距{args.spacing}px, y {y1}-{y2})")


if __name__ == "__main__":
    main()
