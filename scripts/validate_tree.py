#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

CIRCLED = "①②③④⑤⑥⑦⑧⑨"


def load_tree(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(data):
    errors, warnings = [], []
    root = data.get("root")
    if not isinstance(root, str) or not root.strip():
        errors.append("root 不能为空")
    elif len(root.splitlines()) > 2:
        errors.append("root 最多两行")

    branches = data.get("branches")
    if not isinstance(branches, list):
        return ["branches 必须是数组"], warnings
    if not 3 <= len(branches) <= 9:
        errors.append(f"一级枝数量必须为 3–9，当前为 {len(branches)}")
    elif len(branches) < 5:
        warnings.append(f"一级枝建议为 5–9，当前为 {len(branches)}")

    deep_branches = set()
    max_depth = 0
    deep_node_count = 0

    def walk(node, depth, branch_index, path):
        nonlocal max_depth, deep_node_count
        if not isinstance(node, dict):
            errors.append(f"{path} 必须是对象")
            return
        label = node.get("label")
        if not isinstance(label, str) or not label.strip():
            errors.append(f"{path}.label 不能为空")
        elif len("".join(label.split())) > 12:
            errors.append(f"{path}.label 超过 12 字符：{label}")
        children = node.get("children", [])
        if not isinstance(children, list):
            errors.append(f"{path}.children 必须是数组")
            return
        max_depth = max(max_depth, depth)
        if depth >= 4:
            deep_branches.add(branch_index)
        if depth >= 3:
            deep_node_count += 1
        for i, child in enumerate(children):
            walk(child, depth + 1, branch_index, f"{path}.children[{i}]")

    for i, branch in enumerate(branches):
        walk(branch, 1, i, f"branches[{i}]")
        label = branch.get("label", "") if isinstance(branch, dict) else ""
        if i < len(CIRCLED) and isinstance(label, str) and (not label or label[0] != CIRCLED[i]):
            errors.append(f"branches[{i}].label 必须以 {CIRCLED[i]} 开头")

    if max_depth > 5:
        errors.append(f"最大深度不能超过 L5，当前为 L{max_depth}")
    if len(deep_branches) > 2:
        errors.append("L4/L5 只能出现在最多 2 条一级枝；请拆成子图")
    if deep_node_count > 18:
        warnings.append(f"L3 及以上节点共有 {deep_node_count} 个；建议总图收回到 L2 并拆子图")
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description="Validate a mindmap-answer JSON tree")
    parser.add_argument("input")
    args = parser.parse_args()
    try:
        data = load_tree(args.input)
        errors, warnings = validate(data)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"警告：{warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"错误：{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
