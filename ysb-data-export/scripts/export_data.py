#!/usr/bin/env python3
"""ysb-data-export —— 导出 ysb 安装/作业数据为 xlsx（对库只读，仅本地写文件）。

用法：
  python export_data.py --check                     # 环境检查
  python export_data.py --list-fields               # 查看字段注册表（分组）
  python export_data.py --company 1514669 --preview # 预览（不写文件）
  python export_data.py --company "某某公司" --with-work \
      --since 2025-10-01 --until 2025-10-07 [--fields 键1,键2] [--exclude 键3] \
      [--no-photos] [--no-idcard] [--area-only] [--out-dir DIR] --yes

说明：
- 依赖 dbx CLI（连接 prod_192.168.5.17_machine）、Python 3、openpyxl。
- dbx query 默认静默截断 10000 行：本脚本始终显式传 --limit 并校验 row_count。
- 作业模式先按时间窗统计行数，超过单片阈值自动细分（月/周/日）分批查询后合并。
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

DBX_CONN = "prod_192.168.5.17_machine"
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
FIELDS_PATH = os.path.join(SCRIPTS_DIR, "fields.json")

EXCEL_MAX_ROWS = 1_048_576   # Excel 单 sheet 行数上限（含表头）
CHUNK_ROW_TARGET = 100_000   # 单次查询目标行数上限，超出自动细分时间窗
DBX_TIMEOUT = "2m"


class DbxError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# dbx 调用
# ---------------------------------------------------------------------------

def dbx_json(sql, limit, timeout=DBX_TIMEOUT):
    """执行 dbx query 并返回解析后的 JSON。SQL 中不得包含双引号。"""
    sql = " ".join(sql.split())  # 压缩空白为单行
    if '"' in sql:
        raise DbxError("内部错误：SQL 不能包含双引号")
    cmd = f'dbx query {DBX_CONN} "{sql}" --json --timeout {timeout} --limit {int(limit)}'
    proc = subprocess.run(cmd, capture_output=True, encoding="utf-8",
                          errors="replace", shell=True)
    text = (proc.stdout or "").strip()
    resp = None
    if text:
        try:
            resp = json.loads(text)
        except json.JSONDecodeError:
            resp = None
    if proc.returncode != 0 or resp is None or resp.get("error"):
        msg = ""
        if resp and resp.get("error"):
            err = resp["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
        if not msg:
            msg = (proc.stderr or "").strip() or text[:500]
        raise DbxError(msg or f"dbx query 失败（exit={proc.returncode}）")
    return resp


def dbx_rows(sql, limit=10, timeout=DBX_TIMEOUT):
    """返回 (rows, row_count)；rows 为 dict 列表（键=列表达式）。"""
    resp = dbx_json(sql, limit=limit, timeout=timeout)
    cols = resp.get("columns") or []
    rows = resp.get("rows") or []
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append(r)
        else:  # 防御：数组行
            out.append(dict(zip(cols, r)))
    return out, resp.get("row_count", len(out))


def dbx_scalar(sql, timeout=DBX_TIMEOUT):
    """执行单值查询（如 count(*)），返回第一个值。"""
    rows, _ = dbx_rows(sql, limit=10, timeout=timeout)
    if not rows:
        return None
    return list(rows[0].values())[0]


# ---------------------------------------------------------------------------
# 字段注册表
# ---------------------------------------------------------------------------

def load_registry():
    with open(FIELDS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def applicable_fields(registry, with_work):
    out = []
    for f in registry["fields"]:
        if f["mode"] == "install" or (with_work and f["mode"] == "work"):
            out.append(f)
    return out


def lookup_field(token, field_map):
    t = token.strip()
    if t in field_map:
        return field_map[t]
    for f in field_map.values():
        if f["header"] == t:
            return f
    return None


def select_fields(registry, with_work, fields_arg, exclude_arg, no_photos, no_idcard):
    mode_fields = applicable_fields(registry, with_work)
    mode_map = {}
    for f in mode_fields:
        mode_map[f["key"]] = f
        mode_map[f["header"]] = f

    if fields_arg:
        chosen = set()
        for token in split_tokens(fields_arg):
            f = lookup_field(token, mode_map)
            if f is None:
                f_any = lookup_field(token, all_field_map(registry))
                if f_any is not None and f_any["mode"] == "work":
                    raise SystemExit(f"[ERROR] 字段「{token}」属于作业列，仅在 --with-work 模式可选。")
                raise SystemExit(f"[ERROR] 未知字段「{token}」；可用字段见 --list-fields。")
            chosen.add(f["key"])
        selection = [f for f in mode_fields if f["key"] in chosen]
    else:
        selection = [f for f in mode_fields if f.get("default", True) is not False]

    if exclude_arg:
        drop = set()
        for token in split_tokens(exclude_arg):
            f = lookup_field(token, mode_map)
            if f is None:
                raise SystemExit(f"[ERROR] --exclude 未知字段「{token}」；可用字段见 --list-fields。")
            drop.add(f["key"])
        selection = [f for f in selection if f["key"] not in drop]

    if no_photos:
        selection = [f for f in selection if f["group"] != "photo"]
    if no_idcard:
        selection = [f for f in selection if f["key"] != "driver_card"]

    if not selection:
        raise SystemExit("[ERROR] 字段选择为空，请去掉部分排除项。")
    return selection


def all_field_map(registry):
    m = {}
    for f in registry["fields"]:
        m[f["key"]] = f
        m[f["header"]] = f
    return m


def split_tokens(raw):
    for part in re.split(r"[,，]", raw or ""):
        p = part.strip()
        if p:
            yield p


# ---------------------------------------------------------------------------
# 公司解析
# ---------------------------------------------------------------------------

def resolve_company_token(token):
    """解析一个公司标识（名称或 id）。返回 dict 列表；空列表=未找到。"""
    t = token.strip()
    if not t:
        return []
    if t.isdigit():
        rows, _ = dbx_rows(f"select id, name from basic.company where id = {int(t)}", limit=10)
        return [{"id": r["id"], "name": r["name"]} for r in rows]
    esc = t.replace("'", "''")
    rows, _ = dbx_rows(
        f"select id, name from basic.company where name = '{esc}'", limit=50)
    if not rows:
        rows, _ = dbx_rows(
            f"select id, name from basic.company where name like '%{esc}%'", limit=50)
    return [{"id": r["id"], "name": r["name"]} for r in rows]


def resolve_companies(tokens):
    """解析全部公司标识；歧义时报候选清单并 exit 2。返回去重后的公司列表。"""
    resolved = []
    seen = set()
    for token in tokens:
        matches = resolve_company_token(token)
        if not matches:
            raise SystemExit(f"[ERROR] 公司「{token}」在 basic.company 中未找到。")
        if len(matches) > 1:
            print(f"[ERROR] 公司「{token}」匹配到 {len(matches)} 条，请改用公司 id 重试：")
            for m in matches:
                print(f"  id={m['id']}  {m['name']}")
            raise SystemExit(2)
        m = matches[0]
        if m["id"] not in seen:
            seen.add(m["id"])
            resolved.append(m)
    return resolved


# ---------------------------------------------------------------------------
# SQL 拼装
# ---------------------------------------------------------------------------

FROM_BLOCK = (
    "from ysb.install_iot ii "
    "join ysb.install_iot_machine iim on iim.imei = ii.imei and iim.is_deleted = 0 "
    "join ysb.install_iot_owner iio on iio.imei = ii.imei and iio.is_deleted = 0 "
    "join ysb.customer c on c.id = iio.customer_id "
    "join basic.category mc on mc.id = iim.category_id3 "
    "left join basic.iot_category ic on ic.id = ii.type_id3 "
    "left join public.iot i on i.imei = ii.imei "
    "left join basic.company c2 on c2.id = coalesce(ii.install_distributor_company_id, ii.company_id) "
    "left join ("
    "select iii.engine_imei as engine_imei, "
    "string_agg(iii.imei, ',' order by iii.imei) as impl_imeis, "
    "string_agg(ca2.name, ',' order by iii.imei) as impl_cats, "
    "string_agg((select w.name from basic.category_crop_work_type cc "
    "join basic.work_type w on cc.work_type_id2 = w.id "
    "where cc.category_id3 = iii.category_id3 order by w.id limit 1), ',' order by iii.imei) as impl_wts, "
    "string_agg(pw.content, ',' order by iii.imei) as impl_widths, "
    "count(*) as cnt "
    "from ysb.install_iot_implement iii "
    "left join basic.category ca2 on ca2.id = iii.category_id3 "
    "left join ("
    "select distinct on (r.imei) r.imei as imei, r.content as content "
    "from ysb.install_iot_implement_params_value_ref r "
    "join ysb.iot_implement_params_iot iipi on r.iot_implement_params_iot_id = iipi.id "
    "where iipi.iot_implement_params_id = 5 "
    "order by r.imei, r.id desc"
    ") pw on pw.imei = iii.imei "
    "where iii.is_deleted = 0 and iii.imei <> iii.engine_imei "
    "group by iii.engine_imei"
    ") impl on impl.engine_imei = ii.imei "
    "left join ("
    "select distinct on (r.imei) r.imei as imei, r.content as content "
    "from ysb.install_iot_implement_params_value_ref r "
    "join ysb.iot_implement_params_iot iipi on r.iot_implement_params_iot_id = iipi.id "
    "where iipi.iot_implement_params_id = 5 "
    "order by r.imei, r.id desc"
    ") dw on dw.imei = ii.imei"
)


def company_cond(ids, scope):
    if not ids:
        return ""
    lst = ",".join(str(i) for i in ids)
    if scope == "any":
        return (f"(ii.company_id in ({lst}) "
                f"or ii.install_distributor_company_id in ({lst}) "
                f"or ii.distributor_company_id in ({lst}))")
    return f"ii.company_id in ({lst})"


def select_clause(fields):
    """每列用字段键作别名：dbx --json 的行是 {列名: 值}，SELECT 中同名列会互相覆盖，
    必须保证列名唯一（如 4 个 name、2 个 mobile 不加别名会串值）。"""
    return ", ".join(f'{f["sql"]} as {f["key"]}' for f in fields)


def build_sql(fields, with_work, ids, scope, extra_conds, order_by=""):
    sel = select_clause(fields)
    conds = ["ii.status = 10", "ii.is_deleted = 0", "ii.is_has_owner = 1",
             company_cond(ids, scope)]
    conds += [c for c in extra_conds if c]
    conds = [c for c in conds if c]
    sid_join = " join public.stat_iot_day sid on sid.imei = ii.imei" if with_work else ""
    sql = "select " + sel + " " + FROM_BLOCK + sid_join + " where " + " and ".join(conds)
    if order_by:
        sql += " order by " + order_by
    return sql


def build_count_sql(with_work, ids, scope, extra_conds):
    conds = ["ii.status = 10", "ii.is_deleted = 0", "ii.is_has_owner = 1",
             company_cond(ids, scope)]
    conds += [c for c in extra_conds if c]
    conds = [c for c in conds if c]
    sid_join = " join public.stat_iot_day sid on sid.imei = ii.imei" if with_work else ""
    return "select count(*) " + FROM_BLOCK + sid_join + " where " + " and ".join(conds)


def count_rows(with_work, ids, scope, extra_conds):
    return int(dbx_scalar(build_count_sql(with_work, ids, scope, extra_conds)) or 0)


# ---------------------------------------------------------------------------
# 分批规划
# ---------------------------------------------------------------------------

def work_date_cond(d1, d2):
    return (f"(sid.run_day >= {int(d1.strftime('%Y%m%d'))} "
            f"and sid.run_day <= {int(d2.strftime('%Y%m%d'))})")


def install_date_cond(d1, d2):
    """安装时间窗：>= d1 00:00:00 且 < d2 次日 00:00:00。"""
    start = f"{d1.isoformat()} 00:00:00"
    end = f"{(d2 + dt.timedelta(days=1)).isoformat()} 00:00:00"
    return f"(ii.create_time >= '{start}' and ii.create_time < '{end}')"


def plan_work_chunks(ids, scope, since, until, area_only, base_conds):
    """按时间窗二分细分，直到单片行数 <= CHUNK_ROW_TARGET 或缩到单日。
    返回 [(start_date, end_date, rows)]，按时间升序。"""
    area_cond = ["sid.area > 0"] if area_only else []
    out = []
    stack = [(since, until)]
    guard = 0
    while stack:
        guard += 1
        if guard > 400:
            raise SystemExit("[ERROR] 时间窗细分层数过多，请缩小日期范围。")
        s, e = stack.pop()
        n = count_rows(True, ids, scope, base_conds + area_cond + [work_date_cond(s, e)])
        if n > CHUNK_ROW_TARGET and s < e:
            mid = s + dt.timedelta(days=(e - s).days // 2)
            stack.append((mid + dt.timedelta(days=1), e))
            stack.append((s, mid))
        elif n > 0:
            out.append((s, e, n))
    out.sort(key=lambda c: c[0])
    return out


def install_base_conds(since, until):
    conds = []
    if since:
        conds.append(f"ii.create_time >= '{since.isoformat()} 00:00:00'")
    if until:
        conds.append(f"ii.create_time < '{(until + dt.timedelta(days=1)).isoformat()} 00:00:00'")
    return conds


def plan_install_chunks(ids, scope, since, until, base_conds):
    """安装模式：设备行数通常不大；超大且日期上下界齐全时按天二分。"""
    total = count_rows(False, ids, scope, base_conds + install_base_conds(since, until))
    if total <= CHUNK_ROW_TARGET or not (since and until):
        return [(None, None, total)] if total else []
    out = []
    stack = [(since, until)]
    guard = 0
    while stack:
        guard += 1
        if guard > 400:
            raise SystemExit("[ERROR] 时间窗细分层数过多，请缩小日期范围。")
        s, e = stack.pop()
        n = count_rows(False, ids, scope, base_conds + [install_date_cond(s, e)])
        if n > CHUNK_ROW_TARGET and s < e:
            mid = s + dt.timedelta(days=(e - s).days // 2)
            stack.append((mid + dt.timedelta(days=1), e))
            stack.append((s, mid))
        elif n > 0:
            out.append((s, e, n))
    out.sort(key=lambda c: c[0])
    return out


# ---------------------------------------------------------------------------
# 查询与记录
# ---------------------------------------------------------------------------

def rows_to_records(rows, columns, fields):
    recs = []
    for r in rows:
        rec = {}
        vals = list(r.values())
        for i, f in enumerate(fields):
            if f["key"] in r:
                rec[f["key"]] = r[f["key"]]
            elif i < len(columns) and columns[i] in r:
                rec[f["key"]] = r[columns[i]]
            else:
                rec[f["key"]] = vals[i] if i < len(vals) else None
        recs.append(rec)
    return recs


def fetch_chunk(fields, with_work, ids, scope, extra_conds, order_by, expected):
    """执行一片查询；expected 为预统计行数，limit=expected+1000 并校验防截断。"""
    limit = int(expected + 1000)
    sql = build_sql(fields, with_work, ids, scope, extra_conds, order_by)
    resp = dbx_json(sql, limit=limit)
    rc = resp.get("row_count", len(resp.get("rows") or []))
    if rc >= limit:
        raise SystemExit(
            "[ERROR] 查询结果疑似被截断（row_count 触顶 %d），"
            "数据可能比统计时增加，请缩小日期范围重试。" % limit)
    return rows_to_records(resp.get("rows") or [], resp.get("columns") or [], fields)


def fetch_sample(fields, with_work, ids, scope, extra_conds, n=5):
    sql = build_sql(fields, with_work, ids, scope, extra_conds)  # 不带排序，取任意样本更快
    resp = dbx_json(sql, limit=n)
    return rows_to_records(resp.get("rows") or [], resp.get("columns") or [], fields)


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def sort_records(recs):
    def key(rec):
        rd = rec.get("run_day")
        return (str(rec.get("company_name") or ""),
                str(rec.get("owner_name") or ""),
                str(rec.get("imei") or ""),
                rd if isinstance(rd, int) else 0)
    recs.sort(key=key)
    return recs


def write_xlsx(path, sheet_name, fields, recs):
    try:
        from openpyxl import Workbook
        from openpyxl.cell import WriteOnlyCell
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise SystemExit("[ERROR] 缺少 openpyxl，请先安装：pip install openpyxl")
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=sheet_name)

    # 表头样式：加粗、居中、浅灰底色
    header_font = Font(bold=True)
    header_fill = PatternFill("solid", fgColor="D9D9D9")
    header_align = Alignment(horizontal="center", vertical="center")
    header_cells = []
    for f in fields:
        c = WriteOnlyCell(ws, value=f["header"])
        c.font = header_font
        c.fill = header_fill
        c.alignment = header_align
        header_cells.append(c)
    ws.append(header_cells)

    def cell(f, rec):
        v = rec.get(f["key"])
        # dbx 对 numeric 列返回字符串（如 "0.00"），标注 numeric 的字段转成数字
        if f.get("numeric") and isinstance(v, str) and v.strip():
            try:
                return float(v)
            except ValueError:
                return v
        return v

    for rec in recs:
        ws.append([cell(f, rec) for f in fields])
    wb.save(path)


def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", name).strip("_") or "未知公司"


def output_path(out_dir, registry, mode, companies, region_text, type_ids):
    os.makedirs(out_dir, exist_ok=True)
    prefix = registry["modes"][mode]["file_prefix"]
    ts = time.strftime("%Y%m%d_%H%M%S")
    parts = []
    if len(companies) == 1:
        parts.append(safe_filename(companies[0]["name"]))
    if region_text:
        parts.append(safe_filename(region_text))
    if type_ids:
        parts.append("终端" + "+".join(str(t) for t in type_ids))
    name_part = "_".join(parts)
    stem = f"{prefix}_{name_part}_{ts}" if name_part else f"{prefix}_{ts}"
    return os.path.join(out_dir, stem + ".xlsx")


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_check():
    ok = True

    print(f"[PASS] Python {sys.version.split()[0]}")

    try:
        import openpyxl
        print(f"[PASS] openpyxl {openpyxl.__version__}")
    except ImportError:
        ok = False
        print("[FAIL] openpyxl 未安装（pip install openpyxl）")

    proc = subprocess.run("dbx connections list --json", capture_output=True,
                          encoding="utf-8", errors="replace", shell=True)
    if proc.returncode != 0:
        ok = False
        print("[FAIL] dbx CLI 不可用（安装：npm install -g @dbx-app/cli）")
    else:
        print("[PASS] dbx CLI 可用")
        text = proc.stdout or ""
        found = DBX_CONN in text
        if not found:
            try:
                names = []

                def walk(node):
                    if isinstance(node, dict):
                        for k, v in node.items():
                            if k == "name" and isinstance(v, str):
                                names.append(v)
                            walk(v)
                    elif isinstance(node, list):
                        for item in node:
                            walk(item)
                walk(json.loads(text))
                found = DBX_CONN in names
            except (json.JSONDecodeError, Exception):
                found = DBX_CONN in text
        if found:
            print(f"[PASS] dbx 连接 {DBX_CONN} 存在")
        else:
            ok = False
            print(f"[FAIL] dbx 连接 {DBX_CONN} 不存在（请在 DBX Desktop 中配置）")

    try:
        rows, _ = dbx_rows("select 1 as ok", limit=1)
        if rows:
            print(f"[PASS] 连接可查询（select 1）")
        else:
            ok = False
            print("[FAIL] 连接查询无返回")
    except DbxError as e:
        ok = False
        print(f"[FAIL] 连接查询失败：{e}")

    sys.exit(0 if ok else 1)


def cmd_list_fields(registry):
    for g in registry["groups"]:
        fields = [f for f in registry["fields"] if f["group"] == g["key"]]
        if not fields:
            continue
        suffix = "（仅 --with-work）" if g["key"] == "work" else ""
        print(f"[{g['name']}]{suffix}")
        for f in fields:
            mark = "" if f.get("default", True) is not False else "  (默认关)"
            print(f"  {f['key']:<18} {f['header']}{mark}")
        print()
    print("选择：--fields 键1,键2（精确）/ --exclude 键3（排除）/ --no-photos / --no-idcard")
    print("（--fields / --exclude 也接受中文表头。）")


def parse_date(text, opt):
    try:
        return dt.datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit(f"[ERROR] {opt} 日期格式应为 YYYY-MM-DD：{text}")


def cmd_export(args, registry):
    # 公司解析（可选）
    tokens = list(split_tokens(",".join(args.company or [])))
    companies = resolve_companies(tokens) if tokens else []
    ids = [c["id"] for c in companies]
    if companies:
        print("[公司]")
        for c in companies:
            print(f"  - {c['name']} (id={c['id']})")

    # 机主地区 / 终端类型过滤（可选）
    def like_prefix(col, value):
        esc = value.strip().replace("'", "''")
        return f"{col} like '{esc}%'"

    base_filters = []
    region_text = "".join(x.strip() for x in
                          [args.owner_province, args.owner_city, args.owner_county] if x)
    if args.owner_province:
        base_filters.append(like_prefix("c.province", args.owner_province))
    if args.owner_city:
        base_filters.append(like_prefix("c.city", args.owner_city))
    if args.owner_county:
        base_filters.append(like_prefix("c.county", args.owner_county))
    type_ids = []
    if args.terminal_types:
        for tok in split_tokens(args.terminal_types):
            try:
                type_ids.append(int(tok))
            except ValueError:
                raise SystemExit(f"[ERROR] --terminal-types 需为数字 id（如 348,363）：{tok}")
        base_filters.append("ii.type_id3 in (" + ",".join(str(t) for t in type_ids) + ")")
    if not companies and not base_filters:
        raise SystemExit("[ERROR] 至少提供一种过滤：--company / --owner-province / "
                         "--owner-city / --owner-county / --terminal-types。")
    desc = []
    if region_text:
        desc.append("机主地区：" + region_text)
    if type_ids:
        desc.append("终端类型：" + "、".join(str(t) for t in type_ids))
    if desc:
        print("[过滤] " + "；".join(desc))

    # 模式与日期
    with_work = bool(args.with_work)
    mode = "work" if with_work else "install"
    since = parse_date(args.since, "--since") if args.since else None
    until = parse_date(args.until, "--until") if args.until else None
    if with_work and not (since and until):
        raise SystemExit("[ERROR] 作业模式（--with-work）必须同时指定 --since 与 --until。")
    if since and until and since > until:
        raise SystemExit("[ERROR] --since 不能晚于 --until。")

    # 字段选择
    fields = select_fields(registry, with_work, args.fields, args.exclude,
                           args.no_photos, args.no_idcard)
    keys = [f["key"] for f in fields]
    if len(set(keys)) != len(keys):
        raise SystemExit("[ERROR] 字段键重复，请检查 fields.json。")

    # 过滤条件
    scope = args.scope
    area_cond = ["sid.area > 0"] if (with_work and args.area_only) else []
    order_by = "c2.name, c.name, ii.imei" + (", sid.run_day" if with_work else "")

    # 分批规划（含行数统计）
    if with_work:
        chunks = plan_work_chunks(ids, scope, since, until, args.area_only, base_filters)
        base_conds = base_filters + area_cond + [work_date_cond(since, until)]
    else:
        chunks = plan_install_chunks(ids, scope, since, until, base_filters)
        base_conds = base_filters + install_base_conds(since, until)
    total_rows = sum(c[2] for c in chunks)

    # 设备数（work 模式额外统计，供预览）
    if with_work:
        device_count = count_rows(False, ids, scope, base_filters)
    else:
        device_count = total_rows

    # 预览展示
    print(f"[模式] {'作业数据（安装+作业）' if with_work else '安装数据'}")
    if with_work:
        print(f"[日期] {since.isoformat()} ~ {until.isoformat()}（按作业日期 run_day）"
              + ("；仅面积>0" if args.area_only else ""))
    elif since or until:
        print(f"[日期] {since.isoformat() if since else '不限'} ~ "
              f"{until.isoformat() if until else '不限'}（按安装时间 create_time）")
    else:
        print("[日期] 不限（按安装时间 create_time）")
    if companies:
        print(f"[归属] 按 {'company_id / install_distributor / distributor 任一匹配' if scope == 'any' else 'company_id'}")
    print(f"[字段] 共 {len(fields)} 列：" + "、".join(f["header"] for f in fields))
    if with_work:
        print(f"[预估] {total_rows} 行（设备约 {device_count} 台，设备×作业日）；"
              f"查询分 {len(chunks)} 片")
    else:
        print(f"[预估] {total_rows} 行（设备 {device_count} 台）；查询分 {len(chunks)} 片")
    path = output_path(args.out_dir, registry, mode, companies, region_text, type_ids)
    print(f"[输出] {path}")

    if total_rows == 0:
        print("\n查询结果为 0 行，未生成文件。")
        return

    if args.preview:
        sample = fetch_sample(fields, with_work, ids, scope, base_conds, n=5)
        print(f"\n[样本] 前 {len(sample)} 行（超长值截断）：")
        for i, rec in enumerate(sample, 1):
            pairs = []
            for f in fields:
                v = rec.get(f["key"])
                s = "" if v is None else str(v)
                if len(s) > 60:
                    s = s[:57] + "..."
                pairs.append(f"{f['header']}={s}")
            print(f"  {i}. " + "；".join(pairs))
        print("\n预览完成（未写任何文件）。确认后加 --yes 执行导出。")
        return

    if not args.yes:
        try:
            ans = input("\n确认按以上内容执行导出? 输入 yes 继续: ").strip().lower()
        except EOFError:
            ans = ""
        if ans != "yes":
            print("[ABORT] 未确认，已取消。")
            return

    # 执行导出
    start = time.time()
    recs = []
    for idx, (s, e, n) in enumerate(chunks, 1):
        if with_work:
            conds = area_cond + [work_date_cond(s, e)]
            label = f"{s.isoformat()} ~ {e.isoformat()}"
        else:
            conds = [install_date_cond(s, e)] if s else base_conds
            label = f"{s.isoformat()} ~ {e.isoformat()}" if s else "全量"
        print(f"[{idx}/{len(chunks)}] {label}：预计 {n} 行，查询中 ...")
        recs.extend(fetch_chunk(fields, with_work, ids, scope,
                                conds, order_by, n))
    sort_records(recs)
    if len(recs) > EXCEL_MAX_ROWS - 1:
        raise SystemExit(f"[ERROR] 结果 {len(recs)} 行超过 Excel 单 sheet 上限"
                         f"（{EXCEL_MAX_ROWS - 1} 行），请缩小日期范围。")

    write_xlsx(path, registry["modes"][mode]["sheet"], fields, recs)
    print(f"\n文件已生成：{os.path.abspath(path)}")
    print(f"行数：{len(recs)}（{len(chunks)} 片查询）；耗时：{time.time() - start:.1f}s")


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ysb 安装/作业数据导出（对库只读，生成 xlsx）。")
    parser.add_argument("--check", action="store_true", help="环境检查")
    parser.add_argument("--list-fields", action="store_true", help="查看字段注册表")
    parser.add_argument("--company", action="append", default=[],
                        help="公司名称或 id；可多次/逗号分隔（与地区/类型过滤至少给一个）")
    parser.add_argument("--owner-province", help="机主省过滤（前缀匹配，如 江苏）")
    parser.add_argument("--owner-city", help="机主市过滤（前缀匹配，如 南京）")
    parser.add_argument("--owner-county", help="机主区县过滤（前缀匹配，如 高淳）")
    parser.add_argument("--terminal-types", help="终端类型 id 列表（basic.iot_category.id，如 348,363）")
    parser.add_argument("--with-work", action="store_true", help="作业模式（安装+作业）")
    parser.add_argument("--since", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--until", help="结束日期 YYYY-MM-DD（含当天）")
    parser.add_argument("--scope", choices=["company", "any"], default="company",
                        help="归属过滤：company=仅 company_id；any=并入经销商字段")
    parser.add_argument("--fields", help="精确选择的字段（键或中文表头，逗号分隔）")
    parser.add_argument("--exclude", help="排除的字段（键或中文表头，逗号分隔）")
    parser.add_argument("--no-photos", action="store_true", help="排除全部照片列")
    parser.add_argument("--no-idcard", action="store_true", help="排除机手身份证号")
    parser.add_argument("--area-only", action="store_true", help="仅导出作业面积>0 的记录")
    parser.add_argument("--out-dir", default=".", help="输出目录（默认当前目录）")
    parser.add_argument("--preview", action="store_true", help="仅预览，不写文件")
    parser.add_argument("--yes", action="store_true", help="跳过确认直接导出")
    args = parser.parse_args()

    registry = load_registry()

    if args.check:
        cmd_check()
        return
    if args.list_fields:
        cmd_list_fields(registry)
        return

    try:
        cmd_export(args, registry)
    except DbxError as e:
        print(f"[ERROR] 数据库查询失败：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
