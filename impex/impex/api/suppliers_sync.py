import frappe
import json
import requests
from urllib.parse import quote
from frappe.utils import now_datetime, cint
from impex.impex.api.items_sync import _request_with_token
from pymysql.err import OperationalError

# Basic fields to sync for Supplier (no datetime fields)
BASIC_SUPPLIER_FIELDS = [
    "name",
    "supplier_name",
    "supplier_group",
    "supplier_type",
    "tax_id",
    "default_currency",
    "disabled",
]

def _auth_headers(api_key: str, api_secret: str):
    return {
        "Authorization": f"token {api_key}:{api_secret}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def _prepare_supplier_payload(row: dict) -> dict:
    payload = {}
    for f in BASIC_SUPPLIER_FIELDS:
        val = row.get(f)
        if f == "disabled" and isinstance(val, (bool, int)):
            val = int(bool(val))
        payload[f] = val
    # Ensure required keys
    if not payload.get("supplier_name"):
        payload["supplier_name"] = row.get("name")
    return payload

def _find_existing_supplier(site_url: str, api_key: str, api_secret: str, supplier_name: str) -> str | None:
    """Find remote Supplier docname by supplier_name to handle different naming schemes."""
    if not supplier_name:
        return None
    try:
        resp = requests.get(
            f"{site_url}/api/resource/Supplier",
            headers=_auth_headers(api_key, api_secret),
            params={
                "fields": '["name"]',
                "filters": json.dumps([["Supplier", "supplier_name", "=", supplier_name]]),
                "limit_page_length": 1,
            },
            timeout=15,
        )
        if resp.ok:
            data = (resp.json() or {}).get("data") or []
            if data:
                return data[0].get("name")
    except Exception:
        pass
    return None

def _upsert_supplier_group(site_url: str, api_key: str, api_secret: str, group: str, parent: str = "All Supplier Groups"):
    if not group:
        return True, None
    name_key = quote(group)
    put_url = f"{site_url}/api/resource/Supplier%20Group/{name_key}"
    payload = {"supplier_group_name": group, "is_group": 0, "parent_supplier_group": parent}
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
    if resp.status_code == 404:
        post_url = f"{site_url}/api/resource/Supplier%20Group"
        resp = _request_with_token("POST", post_url, api_key, api_secret, payload)
    return (resp.ok, (resp.json() if resp.ok else resp.text))

def _ensure_db_connection():
    """Keep/recreate DB connection if MySQL dropped it during long HTTP work."""
    try:
        frappe.db.sql("select 1")
    except Exception:
        try:
            frappe.db.close()
        except Exception:
            pass
        frappe.db.connect()

@frappe.whitelist()
def sync_suppliers_to_servers(supplier_names: list[str] | None = None, full_sync: int = 0, run_in_background: int = 1):
    """
    Sync Supplier master to remote servers defined in Impex Settings > items_sync_settings.
    Returns:
      - status: "queued" | "synced" | "failed"
      - message: description
      - synced: number of suppliers sent (inline)
      - servers: number of servers processed
      - details: per-server list with errors
      - job_id, queue: only when queued
    """
    # Normalize list args if passed as JSON string
    if isinstance(supplier_names, str):
        try:
            supplier_names = json.loads(supplier_names)
        except Exception:
            supplier_names = [supplier_names]

    if cint(run_in_background):
        job = frappe.enqueue(
            "impex.impex.api.suppliers_sync.sync_suppliers_to_servers",
            queue="long",
            timeout=10800,
            job_name=f"Sync Suppliers ({frappe.session.user})",
            supplier_names=supplier_names,
            full_sync=full_sync,
            run_in_background=0
        )
        return {
            "status": "queued",
            "message": "Supplier sync has been queued on the long worker.",
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

    # Determine suppliers to sync
    to_sync = []
    if supplier_names:
        to_sync = frappe.get_all(
            "Supplier",
            filters={"name": ["in", supplier_names]},
            fields=BASIC_SUPPLIER_FIELDS + ["modified"],
            limit=0,
        )
    elif int(full_sync or 0) == 1:
        to_sync = frappe.get_all("Supplier", fields=BASIC_SUPPLIER_FIELDS + ["modified"], limit=0)
    else:
        last_sync_values = [r.last_sync for r in rows if getattr(r, "last_sync", None)]
        if last_sync_values:
            earliest = min(last_sync_values)
            to_sync = frappe.get_all(
                "Supplier",
                filters={"modified": [">=", earliest]},
                fields=BASIC_SUPPLIER_FIELDS + ["modified"],
                limit=0,
            )
        else:
            return {
                "status": "failed",
                "message": "No last_sync found. Pass full_sync=1 or provide supplier_names.",
                "synced": 0,
                "servers": len(rows),
                "details": []
            }

    if not to_sync:
        return {
            "status": "synced",
            "message": "No suppliers to sync.",
            "synced": 0,
            "servers": len(rows),
            "details": []
        }

    total_sent = 0
    server_results = []

    for s in rows:
        _ensure_db_connection()  # keep DB alive during long loop

        site_url = (s.site_url or "").rstrip("/")
        api_key = s.api_key or ""
        api_secret = s.get_password("api_secret") or ""
        if not site_url or not api_key or not api_secret:
            server_results.append({"site_url": s.site_url, "sent": 0, "errors": ["Missing credentials or URL"]})
            continue

        if s.disabled:
            server_results.append({"site_url": s.site_url, "sent": 0, "errors": ["Disabled URL"]})
            continue

        sent = 0
        errors = []
        candidates = to_sync
        if not supplier_names and int(full_sync or 0) != 1 and s.last_sync:
            last_sync_ts = s.last_sync
            candidates = [sp for sp in to_sync if sp.get("modified") and sp.get("modified") >= last_sync_ts]

        # Ensure dependent doctypes exist
        unique_groups = sorted({(sp.get("supplier_group") or "").strip() for sp in candidates if (sp.get("supplier_group") or "").strip()})

        for grp in unique_groups:
            ok, resp_msg = _upsert_supplier_group(site_url, api_key, api_secret, grp)
            if not ok:
                errors.append(f"Supplier Group '{grp}': {resp_msg}")

        # Upsert Suppliers
        for sp in candidates:
            try:
                payload = _prepare_supplier_payload(sp)
                payload.pop("modified", None)
                payload.pop("name", None)

                # Prefer remote existing name if naming differs
                remote_name = sp.get("name") or payload.get("supplier_name")
                name_key = quote(remote_name, safe="")
                put_url = f"{site_url}/api/resource/Supplier/{name_key}"
                resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)

                if resp.status_code == 404:
                    # Try to resolve by supplier_name (handles sites where docname != supplier_name)
                    existing = _find_existing_supplier(site_url, api_key, api_secret, payload.get("supplier_name") or remote_name)
                    if existing:
                        name_key = quote(existing, safe="")
                        put_url = f"{site_url}/api/resource/Supplier/{name_key}"
                        resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
                        
                        try:
                            body = json.dumps(resp.json(), indent=2)
                        except Exception:
                            body = (resp.text or "")[:5000]  # truncate to avoid huge logs
                

                if resp.status_code == 404:
                    # Not found even after search -> create
                    post_url = f"{site_url}/api/resource/Supplier"
                    resp = _request_with_token("POST", post_url, api_key, api_secret, payload)

                # Handle duplicate on POST by switching to PUT using found name
                if not resp.ok and isinstance(getattr(resp, "status_code", None), int) and resp.status_code in (409, 417):
                    # Try find and update if duplicate exists
                    existing = _find_existing_supplier(site_url, api_key, api_secret, payload.get("supplier_name") or remote_name)
                    if existing:
                        name_key = quote(existing, safe="")
                        put_url = f"{site_url}/api/resource/Supplier/{name_key}"
                        resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)

                if resp.ok:
                    sent += 1
                else:
                    try:
                        msg = resp.json()
                    except Exception:
                        msg = resp.text
                    errors.append(f"{sp.get('name')}: {msg}")
            except Exception as e:
                errors.append(f"{sp.get('name')}: {e}")

        # Update last_sync on child row and commit immediately to avoid idle timeouts
        last_sync_ts = now_datetime()
        try:
            _ensure_db_connection()
            frappe.db.set_value("Item Sync Settings", s.name, "last_sync", last_sync_ts, update_modified=False)
            frappe.db.commit()
        except OperationalError:
            # Reconnect and retry once
            try:
                frappe.db.close()
            except Exception:
                pass
            frappe.db.connect()
            frappe.db.set_value("Item Sync Settings", s.name, "last_sync", last_sync_ts, update_modified=False)
            frappe.db.commit()
        except Exception as e:
            errors.append(f"Failed to update last_sync: {e}")

        total_sent += sent
        server_results.append({"site_url": s.site_url, "sent": sent, "errors": errors})

    error_servers = sum(1 for r in server_results if r.get("errors"))
    status = "synced" if not (total_sent == 0 and error_servers == len(rows)) else "failed"
    message = f"Servers: {len(rows)}, Suppliers sent: {total_sent}. " + (f"{error_servers} server(s) had errors." if error_servers else "All servers OK.")

    # Aggregate error log (fix arg order: message, title)
    try:
        all_errors = []
        for res in server_results:
            for err in (res.get("errors") or []):
                all_errors.append(f"[{res.get('site_url') or 'unknown'}] {err}")
        if all_errors:
            frappe.log_error("\n".join(all_errors), "Supplier Sync Errors")
    except Exception:
        pass

    return {
        "status": status,
        "message": message,
        "synced": total_sent,
        "servers": len(rows),
        "details": server_results
    }