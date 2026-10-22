#!/usr/bin/env python3
"""Shared helpers for the DT sale-info update flow.

Responsibilities:
  - run read-only SQL through the dbx CLI (two connections: dss + machine)
  - resolve a product by sku            -> contract.product      (dss)
  - resolve an owner company by name    -> basic.company         (machine)
  - build the updateSaleInformation body
  - date helpers (day start, +1 calendar year)
"""

import json
import re
import subprocess
from datetime import date, datetime

DBX_DSS = "prod_192.168.5.129_dss_owner"
DBX_MACHINE = "prod_192.168.5.17_machine"
MAX_COMPANY_CANDIDATES = 20


class AbortError(Exception):
    """Raised when the plan cannot be built; the caller prints [ABORT]."""

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


def dbx_query(conn: str, sql: str) -> list:
    """Run a read-only query through the dbx CLI and return its rows."""
    out = subprocess.run(
        f'dbx query {conn} "{sql}" --json',
        capture_output=True, encoding="utf-8", shell=True,
    )
    if out.returncode != 0:
        raise AbortError(f"dbx query failed on {conn}", [out.stderr.strip()])
    try:
        resp = json.loads(out.stdout)
    except json.JSONDecodeError:
        raise AbortError(
            f"dbx returned non-JSON output on {conn}",
            [out.stdout.strip()[:500]],
        )
    if resp.get("error"):
        raise AbortError(f"dbx error on {conn}", [resp["error"].get("message", "")])
    return resp.get("rows", [])


def sql_str(value) -> str:
    """Quote a Python string as a PostgreSQL literal."""
    return "'" + str(value).replace("'", "''") + "'"


def parse_imeis(raw: str) -> list[str]:
    """Split a comma/whitespace separated IMEI list, trimming and de-duplicating."""
    items = [x for x in re.split(r"[,，;；\s]+", raw or "") if x]
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def parse_day(raw: str | None) -> date:
    """--date YYYY-MM-DD, defaulting to today."""
    if raw:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    return date.today()


def day_start(d: date) -> str:
    return f"{d.isoformat()} 00:00:00"


def plus_one_year(d: date) -> date:
    """Same calendar day next year; Feb 29 falls back to Feb 28."""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        return d.replace(year=d.year + 1, day=28)


def fetch_products(sku: str) -> list[dict]:
    rows = dbx_query(
        DBX_DSS,
        "select sku, type_id1, type_id2, type_id3, product_name, product_type "
        "from contract.product "
        f"where sku = {sql_str(sku)} and is_deleted = 0 order by id",
    )
    return [
        {
            "sku": r.get("sku"),
            "typeId1": r.get("type_id1"),
            "typeId2": r.get("type_id2"),
            "typeId3": r.get("type_id3"),
            "terminalName": r.get("product_name"),
            "terminalModel": r.get("product_type"),
        }
        for r in rows
    ]


def fetch_companies(name: str) -> tuple[list[dict], str]:
    """Exact match first, then a LIKE match. Active rows (status=10) rank first."""
    exact = dbx_query(
        DBX_MACHINE,
        "select id, name, status from basic.company "
        f"where name = {sql_str(name)} order by (status = 10) desc, id "
        f"limit {MAX_COMPANY_CANDIDATES}",
    )
    if exact:
        return [_company_row(r) for r in exact], "exact"
    fuzzy = dbx_query(
        DBX_MACHINE,
        "select id, name, status from basic.company "
        f"where name like {sql_str('%' + name + '%')} "
        f"order by (status = 10) desc, length(name), id limit {MAX_COMPANY_CANDIDATES}",
    )
    return [_company_row(r) for r in fuzzy], "fuzzy"


def _company_row(row: dict) -> dict:
    return {"id": row.get("id"), "name": row.get("name"), "status": row.get("status")}


def resolve_product(sku: str) -> dict:
    rows = fetch_products(sku)
    if not rows:
        raise AbortError(f"sku '{sku}' not found in contract.product (dss)")
    if len(rows) > 1:
        raise AbortError(
            f"sku '{sku}' matches {len(rows)} rows in contract.product; expected exactly one",
            [f"id-less rows: {json.dumps(rows, ensure_ascii=False)}"],
        )
    product = rows[0]
    missing = [k for k in ("typeId1", "typeId2", "typeId3", "terminalName", "terminalModel")
               if product.get(k) in (None, "")]
    if missing:
        raise AbortError(f"sku '{sku}' is missing required fields: {', '.join(missing)}")
    return product


def resolve_company(name: str) -> tuple[dict, str, str]:
    """Returns (company, match_kind, note).

    Duplicate rows sharing one name are common in basic.company (a disabled
    row plus an active one). When every match has the same name, keep the
    single row with status=10; otherwise the caller must disambiguate.
    """
    rows, kind = fetch_companies(name)
    if not rows:
        raise AbortError(f"company '{name}' not found in basic.company (machine)")
    if len(rows) == 1:
        return rows[0], kind, ""
    if len({r["name"] for r in rows}) == 1:
        active = [r for r in rows if r.get("status") == 10]
        if len(active) == 1:
            return active[0], kind, "同名多条，已取 status=10（正常）的一条"
    raise AbortError(
        f"company '{name}' matches {len(rows)} rows — specify a more precise name",
        [f"id={r['id']}  status={r.get('status')}  {r['name']}" for r in rows],
    )


def build_body(product: dict, company: dict, imei: str, start: date) -> dict:
    """The exact 13-field body. ownerCompanyTypeCode/Name are intentionally absent."""
    return {
        "sku": product["sku"],
        "imei": imei,
        "typeId1": product["typeId1"],
        "typeId2": product["typeId2"],
        "typeId3": product["typeId3"],
        "sellTime": day_start(start),
        "sendTime": day_start(start),
        "ownerCompany": company["name"],
        "terminalName": product["terminalName"],
        "terminalModel": product["terminalModel"],
        "ownerCompanyId": company["id"],
        "commServiceEndDate": day_start(plus_one_year(start)),
        "commServiceBeginDate": day_start(start),
    }


def build_plan(sku: str, owner_company: str, imeis: list[str], start: date) -> dict:
    if not imeis:
        raise AbortError("no IMEI given")
    product = resolve_product(sku)
    company, match_kind, company_note = resolve_company(owner_company)
    bodies = [(imei, build_body(product, company, imei, start)) for imei in imeis]
    return {
        "product": product,
        "company": company,
        "company_match": match_kind,
        "company_note": company_note,
        "start": start,
        "bodies": bodies,
    }
