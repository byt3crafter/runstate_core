import frappe
import json
import requests
from urllib.parse import quote
from frappe.utils import now_datetime, cint

BASIC_ITEM_FIELDS = [
    "name",
    "item_code",
    "item_name",
    "item_group",
    "stock_uom",
    "description",
    "disabled",
    "brand",
    "is_stock_item",
    "part_1",
    "part_2",
    "part_3",
    "part_4",
    "part_5",
    "part_6",
    "part_7",
    "part_8",
    "part_9",
    "part_10",
    "special_parameter",
    "cb_plu",
]

def _prepare_item_payload(item_row: dict) -> dict:
    # Build payload only from BASIC_ITEM_FIELDS; exclude 'modified' and datetimes
    payload = {}
    for field in BASIC_ITEM_FIELDS:
        val = item_row.get(field)
        # normalize simple types if needed
        if field == "disabled" and isinstance(val, (bool, int)):
            val = int(bool(val))
        payload[field] = val
    # ensure item_code is set
    if not payload.get("item_code"):
        payload["item_code"] = item_row.get("name")
    return payload

def _request_with_token(method: str, url: str, api_key: str, api_secret: str, payload: dict | None = None, timeout: int = 15):
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # default=str ensures any stray non-serializable values won’t break JSON
    data = json.dumps({"data": payload}, default=str) if payload is not None else None
    resp = requests.request(method, url, headers=headers, data=data, timeout=timeout)
    return resp

def _upsert_brand(site_url: str, api_key: str, api_secret: str, brand: str):
    """Ensure Brand exists on target site."""
    if not brand:
        return True, None
    name_key = quote(brand)
    put_url = f"{site_url}/api/resource/Brand/{name_key}"
    payload = {"brand": brand}
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
    if resp.status_code == 404:
        post_url = f"{site_url}/api/resource/Brand"
        resp = _request_with_token("POST", post_url, api_key, api_secret, payload)
    return (resp.ok, (resp.json() if resp.ok else resp.text))

def _upsert_item_group(site_url: str, api_key: str, api_secret: str, group: str, parent: str = "All Item Groups"):
    """Ensure Item Group exists on target site. Creates as non-group under All Item Groups."""
    if not group:
        return True, None
    name_key = quote(group)
    put_url = f"{site_url}/api/resource/Item%20Group/{name_key}"
    payload = {"item_group_name": group, "is_group": 0, "parent_item_group": parent}
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
    if resp.status_code == 404:
        post_url = f"{site_url}/api/resource/Item%20Group"
        resp = _request_with_token("POST", post_url, api_key, api_secret, payload)
    return (resp.ok, (resp.json() if resp.ok else resp.text))

@frappe.whitelist()
def sync_items_to_servers(item_codes: list[str] | None = None, full_sync: int = 0, run_in_background: int = 1):
    """
    Sync basic Item data to remote servers.
    Returns a standardized status dict:
      - status: "queued" | "synced" | "failed"
      - message: short description
      - synced: number of items successfully sent (when run inline)
      - servers: number of servers processed (when run inline)
      - details: per-server detail list (when run inline)
      - job_id, queue: present only when queued
    """
    # Normalize item_codes from JSON string if needed
    if isinstance(item_codes, str):
        try:
            item_codes = json.loads(item_codes)
        except Exception:
            item_codes = [item_codes]

    if cint(run_in_background):
        job = frappe.enqueue(
            "impex.impex.api.items_sync.sync_items_to_servers",
            queue="long",
            timeout=60 * 60,  # 1 hour
            job_name=f"Sync Items ({frappe.session.user})",
            item_codes=item_codes,
            full_sync=full_sync,
            run_in_background=0  # prevent re-enqueue in worker
        )
        return {
            "status": "queued",
            "message": "Item sync has been queued on the long worker.",
            "job_id": getattr(job, "id", None),
            "queue": "long"
        }

    settings = frappe.get_single("Impex Settings")
    rows = settings.get("items_sync_settings") or []
    if not rows:
        return {
            "status": "failed",
            "message": "No Item Sync Settings found in Impex Settings.",
            "synced": 0,
            "servers": 0,
            "details": []
        }

    # Determine items to sync
    items_to_sync = []
    if item_codes:
        items_to_sync = frappe.get_all(
            "Item",
            filters={"item_code": ["in", item_codes]},
            fields=BASIC_ITEM_FIELDS + ["modified"],
            limit=0,
        )
    elif int(full_sync or 0) == 1:
        items_to_sync = frappe.get_all("Item", fields=BASIC_ITEM_FIELDS + ["modified"], limit=0)
    else:
        last_sync_values = []
        for r in rows:
            if getattr(r, "last_sync", None):
                last_sync_values.append(r.last_sync)
        if last_sync_values:
            earliest = min(last_sync_values)
            items_to_sync = frappe.get_all(
                "Item",
                filters={"modified": [">=", earliest]},
                fields=BASIC_ITEM_FIELDS + ["modified"],
                limit=0,
            )
        else:
            return {
                "status": "failed",
                "message": "No last_sync found. Pass full_sync=1 or provide item_codes.",
                "synced": 0,
                "servers": len(rows),
                "details": []
            }

    if not items_to_sync:
        return {
            "status": "synced",
            "message": "No items to sync.",
            "synced": 0,
            "servers": len(rows),
            "details": []
        }

    total_sent = 0
    server_results = []

    for s in rows:
        site_url = (s.site_url or "").rstrip("/")
        api_key = s.api_key or ""
        api_secret = s.get_password("api_secret") or ""
        if not site_url or not api_key or not api_secret:
            server_results.append({"site_url": s.site_url, "sent": 0, "errors": ["Missing credentials or URL"]})
            continue

        if s.disabled:
            server_results.append({"site_url": s.site_url, "sent": 0, "errors": ["Disabled URL"]})
            # Skip syncing to disabled targets
            continue

        sent = 0
        errors = []
        candidates = items_to_sync
        if not item_codes and int(full_sync or 0) != 1 and s.last_sync:
            last_sync_ts = s.last_sync
            candidates = [it for it in items_to_sync if it.get("modified") and it.get("modified") >= last_sync_ts]

        unique_groups = sorted({(it.get("item_group") or "").strip() for it in candidates if (it.get("item_group") or "").strip()})
        unique_brands = sorted({(it.get("brand") or "").strip() for it in candidates if (it.get("brand") or "").strip()})

        for grp in unique_groups:
            ok, resp_msg = _upsert_item_group(site_url, api_key, api_secret, grp)
            if not ok:
                errors.append(f"Item Group '{grp}': {resp_msg}")

        for br in unique_brands:
            ok, resp_msg = _upsert_brand(site_url, api_key, api_secret, br)
            if not ok:
                errors.append(f"Brand '{br}': {resp_msg}")

        for it in candidates:
            try:
                payload = _prepare_item_payload(it)
                payload.pop("modified", None)

                name_key = quote(payload["item_code"])
                put_url = f"{site_url}/api/resource/Item/{name_key}"
                resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)

                if resp.status_code == 404:
                    post_url = f"{site_url}/api/resource/Item"
                    resp = _request_with_token("POST", post_url, api_key, api_secret, payload)
                if resp.ok:
                    sent += 1
                else:
                    try:
                        msg = resp.json()
                    except Exception:
                        msg = resp.text
                    errors.append(f"{payload['item_code']}: {msg}")
            except Exception as e:
                errors.append(f"{it.get('item_code') or it.get('name')}: {e}")

        # Update last_sync for this server if at least the upsert loop ran
        last_sync_ts = now_datetime()
        frappe.db.set_value(
            "Item Sync Settings",
            s.name,
            "last_sync",
            last_sync_ts,
            update_modified=False
        )
        total_sent += sent
        server_results.append({"site_url": s.site_url, "sent": sent, "errors": errors})

    # Persist last_sync updates
    frappe.db.commit()

    error_servers = sum(1 for r in server_results if r.get("errors"))
    status = "synced" if not (total_sent == 0 and error_servers == len(rows)) else "failed"
    message = f"Servers: {len(rows)}, Items sent: {total_sent}. " + (f"{error_servers} server(s) had errors." if error_servers else "All servers OK.")

    # Log all errors into a single Error Log entry
    try:
        all_errors = []
        for res in server_results:
            for err in (res.get("errors") or []):
                all_errors.append(f"[{res.get('site_url') or 'unknown'}] {err}")
        if all_errors:
            frappe.log_error("\n".join(all_errors), "Item Sync Errors")
    except Exception:
        pass

    return {
        "status": status,
        "message": message,
        "synced": total_sent,
        "servers": len(rows),
        "details": server_results
    }