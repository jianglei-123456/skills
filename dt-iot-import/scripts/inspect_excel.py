#!/usr/bin/env python3
"""解析 Excel 内部结构，供构建 /job/externalIotImport/import 的字段映射使用。

输出每个工作表：有效行列数、前几行内容（带引号、空白可见）、表头行/数据起始行
建议、非空数据行数。命令在仓库根目录执行，例如：

    python .agents/skills/dt-iot-import/scripts/inspect_excel.py --file "E:/tmp/农机具信息表(6).xlsx"
    python .agents/skills/dt-iot-import/scripts/inspect_excel.py --file data.xlsx --sheet 1 --rows 8
"""

import argparse
import json
import os
import sys

import openpyxl

# 扫描/展示的最大列数（超宽表防拖慢；真实数据列都远小于该值）
MAX_COLS = 200

# Java String.trim() 等价的裁剪字符集（U+0000..U+0020），避免与 Python strip 行为差异
TRIM_CHARS = "".join(chr(i) for i in range(0x21))


def jtrim(s: str) -> str:
    return s.strip(TRIM_CHARS)


def cell_text(value):
    """单元格值 -> 展示文本；空/空白 -> None。"""
    if value is None:
        return None
    if isinstance(value, str):
        t = jtrim(value)
        return t if t else None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def scan_sheet(ws, show_rows):
    """一次遍历：有效区域、建议表头行、非空数据行数、前 show_rows 行内容。"""
    max_row = ws.max_row or 0
    max_col = min(ws.max_column or 0, MAX_COLS)

    last_nonempty_row = 0
    last_nonempty_col = 0
    row_counts = {}          # 行号 -> 非空数（全表，用于表头判断与数据行统计）
    preview = {}             # 行号 -> 单元格文本列表（前 show_rows 行）

    if max_row and max_col:
        for r_idx, row in enumerate(ws.iter_rows(max_row=max_row, max_col=max_col,
                                                 values_only=True), start=1):
            texts = [cell_text(v) for v in row]
            nonempty_cols = [i for i, t in enumerate(texts, start=1) if t]
            count = len(nonempty_cols)
            row_counts[r_idx] = count
            if count:
                last_nonempty_row = r_idx
                last_nonempty_col = max(last_nonempty_col, nonempty_cols[-1])
            if r_idx <= show_rows:
                preview[r_idx] = texts

    # 表头行建议：前 10 行里非空单元格最多的行（并列取最靠前），至少 2 格
    header_guess = None
    candidates = [(c, -r) for r, c in row_counts.items() if r <= 10 and c >= 2]
    if candidates:
        header_guess = -max(candidates)[1]

    data_row_count = 0
    if header_guess:
        data_row_count = sum(1 for r, c in row_counts.items() if r > header_guess and c)

    return {
        "rows": last_nonempty_row,
        "cols": last_nonempty_col,
        "header_guess": header_guess,
        "data_row_count": data_row_count,
        "preview": preview,
    }


def print_sheet(index, ws, show_rows):
    info = scan_sheet(ws, show_rows)
    header = info["header_guess"]
    print(f'===== [{index}] "{ws.title}" =====')
    print(f'有效区域: {info["rows"]} 行 x {info["cols"]} 列')
    if header:
        print(f'表头行建议: headerRowNo={header}；数据起始行建议: startRow={header + 1}；'
              f'非空数据行: {info["data_row_count"]}')
    else:
        print('表头行建议: 无法判断（请查看下方前几行后人工指定 headerRowNo）')
    for r in range(1, show_rows + 1):
        if r not in info["preview"]:
            break
        texts = info["preview"][r][:info["cols"]] if info["cols"] else []
        cells = [t if t else "" for t in texts]
        while cells and cells[-1] == "":
            cells.pop()
        nonempty = sum(1 for t in texts if t)
        if nonempty == 0:
            print(f'行{r}: (空行)')
        else:
            print(f'行{r} [{nonempty}非空]: {json.dumps(cells, ensure_ascii=False)}')
    if info["cols"] >= MAX_COLS:
        print(f'提示: 内容已触达扫描上限 {MAX_COLS} 列，可能仍有更多列未展示/未统计')
    print()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="解析 Excel 结构（工作表 / 表头行 / 前几行内容），用于构建导入映射")
    parser.add_argument("--file", required=True, help="Excel 文件路径（.xlsx / .xls）")
    parser.add_argument("--sheet", type=int, help="只看第 N 个工作表（1 开始；缺省看全部）")
    parser.add_argument("--rows", type=int, default=5, help="每个工作表展示前几行（默认 5）")
    args = parser.parse_args()

    path = args.file
    if not os.path.isfile(path):
        sys.stderr.write(f"文件不存在: {path}\n")
        sys.exit(1)
    if not path.lower().endswith((".xlsx", ".xls")):
        sys.stderr.write("仅支持 .xlsx / .xls 文件\n")
        sys.exit(1)

    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as e:
        sys.stderr.write(f"Excel 打开失败: {e}\n")
        sys.exit(1)

    try:
        names = wb.sheetnames
        print(f"文件: {path}")
        print(f"工作表数: {len(names)}")
        print(f"工作表列表: {json.dumps(names, ensure_ascii=False)}\n")

        if args.sheet is not None:
            if not (1 <= args.sheet <= len(names)):
                sys.stderr.write(f"--sheet 超出范围（1-{len(names)}）\n")
                sys.exit(1)
            print_sheet(args.sheet, wb.worksheets[args.sheet - 1], args.rows)
        else:
            for i, ws in enumerate(wb.worksheets, start=1):
                print_sheet(i, ws, args.rows)
    finally:
        wb.close()


if __name__ == "__main__":
    main()
