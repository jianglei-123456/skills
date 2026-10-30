#!/usr/bin/env python3
"""Shared helpers for the device-owner change flow (大田 / machine DB).

Responsibilities:
  - run SQL through the dbx CLI (prod_192.168.5.17_machine), read-only by default
  - resolve the new owner        -> ysb.customer
  - read the current owner row   -> ysb.install_iot_owner
  - build the UPDATE that re-points customer_id
"""

import json
import re
import subprocess

DBX_MACHINE = "prod_192.168.5.17_machine"
DBX_DSS = "prod_192.168.5.129_dss_owner"
MAX_OWNER_CANDIDATES = 20
ACTIVE_STATUS = 10


class AbortError(Exception):
    """Raised when the plan cannot be built; the caller prints [ABORT]."""

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


def dbx_rows(conn: str, sql: str, write: bool = False) -> list:
    """Run one statement through the dbx CLI and return its rows.

    The CLI returns every value as a string, so callers normalise ids
    through as_int() instead of comparing raw values.
    """
    # One line: Windows shells mangle multi-line quoted arguments, and dbx
    # then misses --allow-writes. Line-leading indentation is dropped only.
    flat_sql = " ".join(line.strip() for line in sql.splitlines())
    safe_sql = flat_sql.replace('"', '\\"')
    cmd = f'dbx query {conn} "{safe_sql}"'
    if write:
        cmd += " --allow-writes"
    cmd += " --json"
    out = subprocess.run(cmd, capture_output=True, encoding="utf-8", shell=True)
    if out.returncode != 0:
        raise AbortError(f"dbx query failed on {conn}", [out.stderr.strip()])
    try:
        resp = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise AbortError(f"dbx returned non-JSON output on {conn}",
                         [out.stdout.strip()[:500]])
    if resp.get("error"):
        err = resp["error"]
        message = err.get("message", "") if isinstance(err, dict) else str(err)
        raise AbortError(f"dbx error on {conn}", [message])
    return resp.get("rows", [])


def sql_str(value) -> str:
    """Quote a Python string as a PostgreSQL literal."""
    return "'" + str(value).replace("'", "''") + "'"


def sql_list(values) -> str:
    return ", ".join(sql_str(v) for v in values)


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_imeis(raw: str) -> list[str]:
    """Split a comma/whitespace separated IMEI list, trimming and de-duplicating."""
    items = [x for x in re.split(r"[,，;；\s]+", raw or "") if x]
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _customer_rows(condition: str, fuzzy: bool = False) -> list[dict]:
    order = ("order by (status = 10) desc, length(name), id" if fuzzy
             else "order by (status = 10) desc, id")
    rows = dbx_rows(
        DBX_MACHINE,
        "select id, name, status, company_ids from ysb.customer "
        f"where {condition} {order} limit {MAX_OWNER_CANDIDATES}",
    )
    return [{"id": as_int(r.get("id")), "name": r.get("name"),
             "status": as_int(r.get("status")), "company_ids": r.get("company_ids")}
            for r in rows]


def _company_rows(condition: str, fuzzy: bool = False) -> list[dict]:
    order = ("order by (status = 10) desc, length(name), id" if fuzzy
             else "order by (status = 10) desc, id")
    rows = dbx_rows(
        DBX_MACHINE,
        "select id, name, status from basic.company "
        f"where {condition} {order} limit {MAX_OWNER_CANDIDATES}",
    )
    return [{"id": as_int(r.get("id")), "name": r.get("name"), "status": as_int(r.get("status"))}
            for r in rows]


def resolve_company(raw: str) -> tuple[dict, str, str]:
    """Resolve a distributor company from basic.company by id or (partial) name."""
    token = (raw or "").strip()
    if not token:
        raise AbortError("未提供经销商")

    if token.isdigit():
        rows, kind = _company_rows(f"id = {int(token)}"), "id"
    else:
        rows, kind = _company_rows(f"name = {sql_str(token)}"), "exact"
        if not rows:
            rows = _company_rows(f"name like {sql_str('%' + token + '%')}", fuzzy=True)
            kind = "fuzzy"

    if not rows:
        raise AbortError(f"经销商 '{token}' 在 basic.company 中不存在")

    active = [r for r in rows if r["status"] == ACTIVE_STATUS]
    if len(active) == 1:
        company = active[0]
        note = "" if len(rows) == 1 else "同名多条，已取 status=10（正常）的一条"
    elif len(rows) == 1:
        company, note = rows[0], ""
    else:
        raise AbortError(
            f"经销商 '{token}' 匹配 {len(rows)} 条记录，请改用 id 指定",
            [f"id={r['id']}  status={r['status']}  {r['name']}" for r in rows],
        )
    return company, kind, note


def _parse_ids(raw) -> set[int]:
    """Extract the numeric ids out of a company_ids value (e.g. '87531' / '1,2')."""
    return {int(x) for x in re.findall(r"\d+", str(raw or ""))}


def resolve_owner(raw: str, distributor_ids: set[int] | None = None) -> tuple[dict, str, str]:
    """Resolve the new owner from an id or a (possibly partial) name.

    When several customers share the name, prefer the one whose company_ids
    contains the distributor_id of the devices being changed; if none matches,
    take the first active row. Returns (owner, match_kind, note). Raises
    AbortError when the result is still ambiguous or not active (status <> 10).
    """
    token = (raw or "").strip()
    if not token:
        raise AbortError("未提供新机主")

    if token.isdigit():
        rows, kind = _customer_rows(f"id = {int(token)}"), "id"
    else:
        rows, kind = _customer_rows(f"name = {sql_str(token)}"), "exact"
        if not rows:
            rows = _customer_rows(f"name like {sql_str('%' + token + '%')}", fuzzy=True)
            kind = "fuzzy"

    if not rows:
        raise AbortError(f"新机主 '{token}' 在 ysb.customer 中不存在")

    if len(rows) == 1:
        owner, note = rows[0], ""
    else:
        same_name = len({r["name"] for r in rows}) == 1
        wanted = {d for d in (distributor_ids or set()) if d is not None}
        matched = [r for r in rows if _parse_ids(r.get("company_ids")) & wanted]
        if len(matched) == 1:
            owner = matched[0]
            note = (f"同名多条，已按设备 distributor_id={sorted(wanted)} 命中 company_ids 选取"
                    if same_name else
                    f"多条候选，已按设备 distributor_id={sorted(wanted)} 命中 company_ids 选取")
        elif matched:
            owner = matched[0]
            note = f"多条候选均命中 distributor_id，已取 id={owner['id']}"
        elif same_name:
            owner = rows[0]
            note = f"同名多条且 company_ids 未命中 distributor_id，已任取 id={owner['id']}"
        else:
            raise AbortError(
                f"新机主 '{token}' 匹配 {len(rows)} 条不同名称的记录，请给出更精确的名称或 id",
                describe_candidates(rows),
            )

    if owner["status"] != ACTIVE_STATUS:
        raise AbortError(
            f"新机主 '{owner['name']}' 的 status={owner['status']}，不是 {ACTIVE_STATUS}（正常），拒绝写入"
        )
    return owner, kind, note


def _device_counts(customer_ids: list[int]) -> dict[int, int]:
    """How many active owner rows each customer currently holds."""
    ids = [i for i in customer_ids if i is not None]
    if not ids:
        return {}
    rows = dbx_rows(
        DBX_MACHINE,
        "select customer_id, count(*) as n from ysb.install_iot_owner "
        f"where is_deleted = 0 and customer_id in ({sql_list(ids)}) group by customer_id",
    )
    return {as_int(r.get("customer_id")): as_int(r.get("n")) for r in rows}


def describe_candidates(rows: list[dict]) -> list[str]:
    """Render ambiguous candidates with their device count, to help pick an id."""
    counts = _device_counts([r["id"] for r in rows])
    return [f"id={r['id']}  status={r['status']}  设备={counts.get(r['id'], 0)}  "
            f"company_ids={r.get('company_ids') or '-'}  {r['name']}"
            for r in rows]


def fetch_owner_rows(imeis: list[str]) -> dict[str, dict]:
    """Current owner rows keyed by IMEI (only is_deleted = 0 rows)."""
    if not imeis:
        return {}
    rows = dbx_rows(
        DBX_MACHINE,
        "select o.id, o.imei, o.customer_id, o.distributor_id, c.name as customer_name, o.update_time "
        "from ysb.install_iot_owner o "
        "left join ysb.customer c on c.id = o.customer_id "
        f"where o.is_deleted = 0 and o.imei in ({sql_list(imeis)}) "
        "order by o.imei",
    )
    return {
        r["imei"]: {
            "id": as_int(r.get("id")),
            "imei": r.get("imei"),
            "customer_id": as_int(r.get("customer_id")),
            "distributor_id": as_int(r.get("distributor_id")),
            "customer_name": r.get("customer_name"),
            "update_time": r.get("update_time"),
        }
        for r in rows
    }


def fetch_state(imeis: list[str]) -> dict[str, dict]:
    """Current owner/distributor values of each IMEI across every table involved.

    Keys: owner_customer_id, owner_distributor_id, install_company_id,
    install_distributor_company_id, machine_distributor_id,
    iot_owner_company_id (machine public.iot), dss_iot_owner_company_id.
    """
    if not imeis:
        return {}
    lst = sql_list(imeis)
    state: dict[str, dict] = {}

    def put(imei, **kw):
        if imei:
            state.setdefault(imei, {"imei": imei}).update(kw)

    for r in dbx_rows(
        DBX_MACHINE,
        "select o.imei, o.customer_id, o.distributor_id, c.name as customer_name "
        "from ysb.install_iot_owner o left join ysb.customer c on c.id = o.customer_id "
        f"where o.is_deleted = 0 and o.imei in ({lst})",
    ):
        put(r["imei"], owner_customer_id=as_int(r.get("customer_id")),
            owner_distributor_id=as_int(r.get("distributor_id")),
            customer_name=r.get("customer_name"))

    for r in dbx_rows(
        DBX_MACHINE,
        "select imei, company_id, install_distributor_company_id from ysb.install_iot "
        f"where is_deleted = 0 and imei in ({lst})",
    ):
        put(r["imei"], install_company_id=as_int(r.get("company_id")),
            install_distributor_company_id=as_int(r.get("install_distributor_company_id")))

    for r in dbx_rows(
        DBX_MACHINE,
        "select imei, distributor_id from ysb.install_iot_machine "
        f"where is_deleted = 0 and imei in ({lst})",
    ):
        put(r["imei"], machine_distributor_id=as_int(r.get("distributor_id")))

    for r in dbx_rows(
        DBX_MACHINE,
        f"select imei, owner_company_id from public.iot where imei in ({lst})",
    ):
        put(r["imei"], iot_owner_company_id=as_int(r.get("owner_company_id")))

    for r in _dss_iot_rows(lst):
        put(r["imei"], dss_iot_owner_company_id=as_int(r.get("owner_company_id")))

    return state


def _dss_iot_rows(lst: str) -> list:
    """Rows of the DSS-side iot table; empty when the connection/table is absent."""
    try:
        return dbx_rows(DBX_DSS, f"select imei, owner_company_id from contract.iot where imei in ({lst})")
    except AbortError:
        return []


# Table -> (column holding the distributor id, human label) for the checks below.
DIST_FIELDS = (
    ("owner_distributor_id", "install_iot_owner.distributor_id"),
    ("install_company_id", "install_iot.company_id"),
    ("install_distributor_company_id", "install_iot.install_distributor_company_id"),
    ("machine_distributor_id", "install_iot_machine.distributor_id"),
    ("iot_owner_company_id", "public.iot.owner_company_id"),
    ("dss_iot_owner_company_id", "contract.iot.owner_company_id"),
)


def distributor_mismatches(state_row: dict, distributor_id: int) -> list[str]:
    """Which distributor columns of one device still point elsewhere."""
    # A key is absent when the table has no row for the IMEI (skip); a present
    # but NULL value still counts, since the UPDATE fills it in.
    return [label for key, label in DIST_FIELDS
            if key in state_row and state_row[key] != distributor_id]


def build_update_sql(imeis: list[str], owner_id: int, distributor_id: int | None = None,
                     distributor_name: str | None = None) -> str:
    lst = sql_list(imeis)
    if distributor_id is None:
        return (
            "update ysb.install_iot_owner\n"
            f"   set customer_id = {owner_id},\n"
            "       update_time = now()\n"
            " where is_deleted = 0\n"
            f"   and imei in ({lst})\n"
            "returning id, imei, customer_id"
        )
    name = sql_str(distributor_name or "")
    # One statement: a failure cannot leave the four tables out of sync.
    return (
        "with o as (\n"
        "    update ysb.install_iot_owner\n"
        f"       set customer_id = {owner_id},\n"
        f"           distributor_id = {distributor_id},\n"
        "           update_time = now()\n"
        "     where is_deleted = 0\n"
        f"       and imei in ({lst})\n"
        "    returning imei\n"
        "), i as (\n"
        "    update ysb.install_iot\n"
        f"       set company_id = {distributor_id},\n"
        f"           install_distributor_company_id = {distributor_id},\n"
        "           update_time = now()\n"
        "     where is_deleted = 0\n"
        f"       and imei in ({lst})\n"
        "    returning imei\n"
        "), m as (\n"
        "    update ysb.install_iot_machine\n"
        f"       set distributor_id = {distributor_id},\n"
        "           update_time = now()\n"
        "     where is_deleted = 0\n"
        f"       and imei in ({lst})\n"
        "    returning imei\n"
        "), p as (\n"
        "    update public.iot\n"
        f"       set owner_company_id = {distributor_id},\n"
        f"           owner_company = {name}\n"
        f"     where imei in ({lst})\n"
        "    returning imei\n"
        ")\n"
        "select 'owner' as tbl, imei from o\n"
        "union all select 'install', imei from i\n"
        "union all select 'machine', imei from m\n"
        "union all select 'iot', imei from p"
    )


def build_dss_sql(imeis: list[str], distributor_id: int, distributor_name: str) -> str:
    return (
        "update contract.iot\n"
        f"   set owner_company_id = {distributor_id},\n"
        f"       owner_company = {sql_str(distributor_name)}\n"
        f" where imei in ({sql_list(imeis)})\n"
        "returning imei"
    )


def build_plan(imeis: list[str], owner_raw: str, distributor_raw: str | None = None) -> dict:
    """Work out what to change.

    distributor_raw is optional; when given, the distributor is re-pointed in
    install_iot_owner, install_iot, install_iot_machine, public.iot (machine)
    and contract.iot (dss) as well.
    """
    if not imeis:
        raise AbortError("未提供 IMEI")

    distributor, dist_kind, dist_note = None, "", ""
    if distributor_raw:
        distributor, dist_kind, dist_note = resolve_company(distributor_raw)

    state = fetch_state(imeis)

    # Owner disambiguation follows the distributor the devices will END UP on:
    # the new one when given, otherwise their current one.
    if distributor:
        match_ids = {distributor["id"]}
    else:
        match_ids = {r.get("owner_distributor_id") for r in state.values()
                     if r.get("owner_distributor_id") is not None}
    owner, kind, note = resolve_owner(owner_raw, match_ids)

    targets, unchanged, missing = [], [], []
    for imei in imeis:
        row = state.get(imei)
        if row is None or row.get("owner_customer_id") is None:
            missing.append(imei)
            continue
        need_owner = row.get("owner_customer_id") != owner["id"]
        need_dist = bool(distributor) and bool(
            distributor_mismatches(row, distributor["id"]))
        if need_owner or need_dist:
            targets.append(row)
        else:
            unchanged.append(row)

    if not targets:
        raise AbortError("没有需要修改的设备（全部已是目标机主/经销商，或机主表中不存在）")

    target_imeis = [row["imei"] for row in targets]
    return {
        "owner": owner,
        "owner_match": kind,
        "owner_note": note,
        "distributor": distributor,
        "distributor_match": dist_kind,
        "distributor_note": dist_note,
        "state": state,
        "targets": targets,
        "unchanged": unchanged,
        "missing": missing,
        "imeis": imeis,
        "sql": build_update_sql(target_imeis, owner["id"],
                                distributor["id"] if distributor else None,
                                distributor["name"] if distributor else None),
        "dss_sql": (build_dss_sql(target_imeis, distributor["id"], distributor["name"])
                    if distributor else ""),
    }
