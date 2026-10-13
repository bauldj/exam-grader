# -*- coding: utf-8 -*-
"""
批改痕迹渲染：在原扫描件上叠加仿真教师批改，并可选追加行楷评语面板。

用法：
  python annotate_grading.py --paper 扫描件.jpg --config marks.json --out 终版.jpg

marks.json 格式见技能 references/workflow-details.md，核心字段：
  mask      : 姓名脱敏白矩形列表 [[x1,y1,x2,y2], ...]（可空）
  marks     : 逐题标记 [{no,col,x,y,verdict,score,note}]
              verdict: ok(√) / no(×) / part(半对=√下加点)
              col: L=左栏 / R=右栏（决定批语对齐方向）
              score: "7分" 等得分文本（选择/填空可null）
              note : 批语（如"应为D"）
  sections  : 大题小计 [{"label":"24分","x":32,"y":305}]
  total     : 手写圈总分 {"text":"54","x":1745,"y":150}
  comments  : 可选 {"总评":"...","items":[...],"建议":"..."} → 卷尾行楷评语面板

依赖：Pillow。中文字体：华文行楷(STXINGKA.TTF)与微软雅黑(msyh.ttc)，Windows自带；
      其他系统请把字体文件路径改为实际可用的中文字体。
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HAND_PATH = 'C:/Windows/Fonts/STXINGKA.TTF'   # 华文行楷（手写风格）
FALL_PATH = 'C:/Windows/Fonts/msyh.ttc'
RED = (200, 28, 28)
MARK_SIZE = 62          # 批改符号尺寸
MARK_W = 7              # 笔画宽
PANEL_SZ = 44           # 评语四号字 ≈14pt
PANEL_LH = 72
PANEL_PAD = 64


def load_font(path, sz):
    if os.path.exists(path):
        return ImageFont.truetype(path, sz)
    for alt in ('C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/simsun.ttc'):
        if os.path.exists(alt):
            return ImageFont.truetype(alt, sz)
    return ImageFont.load_default()


class Hand:
    """行楷手写体；缺字形字符自动回退到后备字体（字符级）"""

    def __init__(self, sz):
        self.h = load_font(HAND_PATH, sz)
        self.f = load_font(FALL_PATH, sz)
        self.cache = {}
        self.probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    def font_for(self, ch):
        if ch not in self.cache:
            self.cache[ch] = self.h if self.h.getmask(ch).getbbox() else self.f
        return self.cache[ch]

    def width(self, text):
        return sum(self.probe.textlength(ch, font=self.font_for(ch)) for ch in text)

    def draw(self, d, x, y, text, color):
        for ch in text:
            f = self.font_for(ch)
            d.text((x, y), ch, font=f, fill=color)
            x += d.textlength(ch, font=f)
        return x

    def wrap(self, text, maxw):
        lines, cur = [], ""
        for para in text.split("\n"):
            cur = ""
            for ch in para:
                if self.width(cur + ch) <= maxw:
                    cur += ch
                else:
                    lines.append(cur)
                    cur = ch
            lines.append(cur)
        return lines


def jitter(pts, j=3):
    import random
    return [(x + random.uniform(-j, j), y + random.uniform(-j, j)) for x, y in pts]


def draw_check(d, cx, cy, s):
    d.line([(cx - .42 * s, cy + .02 * s), (cx - .10 * s, cy + .40 * s), (cx + .52 * s, cy - .46 * s)],
           fill=RED, width=MARK_W, joint="curve")


def draw_cross(d, cx, cy, s):
    d.line([(cx - .38 * s, cy - .40 * s), (cx + .05 * s, cy + .02 * s), (cx + .40 * s, cy + .40 * s)],
           fill=RED, width=MARK_W, joint="curve")
    d.line([(cx + .40 * s, cy - .42 * s), (cx - .02 * s, cy - .02 * s), (cx - .40 * s, cy + .40 * s)],
           fill=RED, width=MARK_W, joint="curve")


def draw_part(d, cx, cy, s):
    """半对：√ 下加一点（传统"勾下加点"记部分分）"""
    draw_check(d, cx, cy, s)
    r = .10 * s
    x, y = cx + .06 * s, cy + .64 * s
    d.ellipse([x - r, y - r, x + r, y + r], fill=RED)


DRAW = {"ok": draw_check, "no": draw_cross, "part": draw_part}


def circled(d, cx, cy, rw, rh):
    """手绘风格双线圈（教师圈总分）"""
    for dx, dy, sc in [(0, 0, 1.0), (4, -3, .96), (-3, 3, .99)]:
        d.ellipse([cx - rw * sc + dx, cy - rh * sc + dy, cx + rw * sc + dx, cy + rh * sc + dy],
                  outline=RED, width=5)


def render_comments(panel, hand, comments, pad):
    """在白色面板上渲染行楷评语：总评 + 数字序号要点 + 建议。返回面板使用高度。"""
    title_f = load_font(HAND_PATH, 62)
    pd = ImageDraw.Draw(panel)
    W = panel.width
    maxw = W - pad * 2

    pd.text((pad, 24), "评语", font=title_f, fill=RED)
    pd.line([pad, 116, W - pad, 116], fill=(205, 208, 214), width=2)

    flow = [("总评：" + comments["总评"], 26)]
    for i, it in enumerate(comments.get("items", []), 1):
        flow.append((f"{i}. {it}", 30))
    if comments.get("建议"):
        flow.append(("建议：" + comments["建议"], 34))

    y = 150
    for txt, gap in flow:
        y += gap
        for ln in hand.wrap(txt, maxw):
            hand.draw(pd, pad, y, ln, RED)
            y += PANEL_LH
    return y + 56


def main():
    ap = argparse.ArgumentParser(description="批改痕迹渲染")
    ap.add_argument("--paper", required=True, help="原扫描件路径")
    ap.add_argument("--config", required=True, help="marks.json 配置")
    ap.add_argument("--out", required=True, help="输出终版图路径")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fp:
        cfg = json.load(fp)

    im = Image.open(args.paper).convert("RGB")
    W, H = im.size
    d0 = ImageDraw.Draw(im)
    hand = Hand(PANEL_SZ)

    # 1) 姓名脱敏（白矩形）
    for m in cfg.get("mask", []):
        d0.rectangle(m, fill=(255, 255, 255))

    # 2) 逐题手绘批改符号 + 得分 + 批语
    for m in cfg.get("marks", []):
        mx, ay, v = m["x"], m["y"], m["verdict"]
        DRAW[v](d0, mx, ay, MARK_SIZE)
        yy = ay + 46
        if m.get("score"):
            hand.draw(d0, mx + 14, yy, m["score"], RED)
            yy += 56
        if m.get("note"):
            for ln in hand.wrap(m["note"], 420):
                hand.draw(d0, mx + 14, yy, ln, RED)
                yy += 44

    # 3) 大题小计（写在"一/二/三"编号旁空白处）
    for s in cfg.get("sections", []):
        hand.draw(d0, s["x"], s["y"], s["label"], RED)

    # 4) 手写圈总分（卷首右上）
    t = cfg.get("total")
    if t:
        hand.draw(d0, t["x"], t["y"], t["text"], RED, )
        tw = d0.textlength(t["text"], font=load_font(HAND_PATH, PANEL_SZ))
        circled(d0, t["x"] + tw / 2, t["y"] + PANEL_SZ / 2, tw / 2 + 34, PANEL_SZ / 2 + 22)

    # 5) 评语面板（可选）
    panel_h = 0
    if cfg.get("comments"):
        probe = ImageDraw.Draw(im)
        tmp_lines = []
        total_h = 118 + 56
        for txt, gap in [("总评：" + cfg["comments"]["总评"], 26)] + \
                         [(f"{i}. {it}", 30) for i, it in enumerate(cfg["comments"].get("items", []), 1)] + \
                         ([("建议：" + cfg["comments"]["建议"], 34)] if cfg["comments"].get("建议") else []):
            ls = hand.wrap(txt, W - PANEL_PAD * 2)
            tmp_lines.append((ls, gap))
            total_h += gap + len(ls) * PANEL_LH
        panel_h = total_h
        panel = Image.new("RGB", (W, panel_h), (255, 255, 255))
        render_comments(panel, hand, cfg["comments"], PANEL_PAD)
        canvas = Image.new("RGB", (W, H + panel_h), (255, 255, 255))
        canvas.paste(im, (0, 0))
        canvas.paste(panel, (0, H))
        im = canvas

    im.save(args.out, "JPEG", quality=88, optimize=True)
    kb = os.path.getsize(args.out) / 1024
    print(f"OK {args.out} {im.size[0]}x{im.size[1]} {kb:.0f}KB (评语面板 {panel_h}px)")


if __name__ == "__main__":
    main()
