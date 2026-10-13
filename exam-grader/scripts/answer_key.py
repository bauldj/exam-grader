# -*- coding: utf-8 -*-
"""
答案库归一化比对判分：消除 LaTeX/书写差异导致的比对歧义（如 5π/2 vs 5π/4）。

用法：
  1) 判分：python answer_key.py --key answer_key.json --sheet 学生答案.csv
     (csv 列：姓名,1,2,...,18；单元格填学生答案，LaTeX或普通写法均可)
  2) 调试归一化：python answer_key.py --demo

说明：
- 归一化规则：\\frac{a}{b}→a/b、π→pi、√→sqrt、去空格/全角括号、去"人"等后缀
- 开放题(证明/作图)在答案库中 normalized 设为 PROOF_OPEN，脚本自动跳过转人工
- 解答题部分分：答案库中配 rubric 分步给分，本脚本对解答题只做答案比对提示，
  过程分请按 rubric 由教师/AI 复核（accuracy-rules.md 规则9、10）
"""
import argparse
import csv
import json
import os
import re


def _replace_braced(s, cmd, joiner):
    """把 \\cmd{A}{B} / \\cmd{A} 中的嵌套大括号正确解析后替换（循环直到无匹配）"""
    while True:
        i = s.find("\\" + cmd + "{")
        if i < 0:
            return s
        j = i + len(cmd) + 1
        groups, pos = [], j
        ok = True
        for _ in range(2 if joiner else 1):
            if pos >= len(s) or s[pos] != "{":
                ok = False
                break
            depth = 0
            k = pos
            while k < len(s):
                if s[k] == "{":
                    depth += 1
                elif s[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            groups.append(s[pos + 1:k])
            pos = k + 1
        if not ok:
            return s
        rep = (groups[0] + joiner + groups[1]) if joiner else (cmd + groups[0])
        s = s[:i] + rep + s[pos:]


def normalize(s):
    """归一化：把不同写法统一为可比对形式"""
    if s is None:
        return ""
    s = str(s).strip()
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("\\cdot", "*").replace("\\times", "*")
    s = _replace_braced(s, "frac", "/")     # 先展开分数（支持嵌套根号）
    s = _replace_braced(s, "sqrt", None)    # \sqrt{10} -> sqrt10
    s = s.replace("\\pi", "pi").replace("π", "pi")
    s = s.replace("√", "sqrt")
    s = s.replace("\\circ", "").replace("°", "")
    s = s.replace("\\text", "").replace("{", "").replace("}", "")
    s = s.replace("\\ ", "").replace("\\", "").replace(" ", "")
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("人", "").replace(",", "|").replace("，", "|")
    if s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    return s.lower()


def load_key(path):
    with open(path, encoding="utf-8") as f:
        key = json.load(f)
    std = {}
    for sec in key["sections"]:
        for it in sec["items"]:
            std[it["no"]] = {
                "normalized": it.get("normalized") or normalize(it["answer"]),
                "per_score": it.get("score", sec.get("per_score", 0)),
                "open": (it.get("normalized") == "PROOF_OPEN"),
            }
    return key, std


def grade(key, std, sheet):
    with open(sheet, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"【{key['paper']}】满分 {key['total_score']}\n")
    summary = []
    for row in rows:
        name = row.get("姓名", "?")
        answers = {int(k): v for k, v in row.items() if k.strip().isdigit()}
        total = 0
        print(f"===== {name} =====")
        for no in sorted(std):
            stu = normalize(answers.get(no, ""))
            ref, pts, is_open = std[no]["normalized"], std[no]["per_score"], std[no]["open"]
            if is_open:
                print(f"  第{no}题: 「{answers.get(no, '')}」 开放题-人工判定")
                continue
            ok = (stu == ref)
            got = pts if ok else 0
            total += got
            mark = "√" if ok else "×"
            print(f"  第{no}题: 「{answers.get(no, '')}」 {mark} {got}/{pts}")
        print(f"  >>> 小计(不含开放题): {total}\n")
        summary.append((name, total))
    print("== 汇总（开放题另计）==")
    for name, t in summary:
        print(f"  {name}: {t}")


def demo():
    cases = [
        ("\\frac{5\\pi}{4}", "5π/4"),
        ("\\frac{5\\pi}{4}", "\\frac{5\\pi}{4}"),
        ("\\frac{5\\pi}{4}", "5π/2"),
        ("10n-2", "(10n-2)"),
        ("\\frac{3\\sqrt{10}}{4}", "3√10/4"),
    ]
    for ref, stu in cases:
        print(f"  标准 {ref!r} vs 学生 {stu!r} → {normalize(ref)!r} vs {normalize(stu)!r} "
              f"{'相同' if normalize(ref)==normalize(stu) else '不同'}")


def main():
    ap = argparse.ArgumentParser(description="答案库归一化比对判分")
    ap.add_argument("--key", help="answer_key.json")
    ap.add_argument("--sheet", help="学生答案.csv")
    ap.add_argument("--demo", action="store_true", help="归一化演示")
    args = ap.parse_args()
    if args.demo or not (args.key and args.sheet):
        demo()
        if not args.demo:
            print("\n(未提供 --key/--sheet，仅演示归一化)")
        return
    key, std = load_key(args.key)
    grade(key, std, args.sheet)


if __name__ == "__main__":
    main()
