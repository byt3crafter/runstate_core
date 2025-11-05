import frappe
import json
import requests
from frappe.utils import now_datetime, cint
from urllib.parse import quote
from pymysql.err import OperationalError

def _auth_headers(api_key: str, api_secret: str):
    return {
        "Authorization": f"token {api_key}:{api_secret}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def _request_with_token(method: str, url: str, api_key: str, api_secret: str, payload: dict | None = None, timeout: int = 30):
    headers = _auth_headers(api_key, api_secret)
    data = json.dumps({"data": payload}, default=str) if payload is not None else None
    return requests.request(method, url, headers=headers, data=data, timeout=timeout)

def _find_existing_supplier(site_url: str, api_key: str, api_secret: str, supplier_name: str) -> str | None:
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
            timeout=20,
        )
        if resp.ok:
            data = (resp.json() or {}).get("data") or []
            if data:
                return data[0].get("name")
    except Exception:
        pass
    return None

def _ensure_supplier_remote(site_url: str, api_key: str, api_secret: str, supplier_name: str):
    """Ensure Supplier exists on target. PUT by name, search by supplier_name, then POST."""
    if not supplier_name:
        return True, None

    remote_name = supplier_name
    name_key = quote(remote_name, safe="")
    put_url = f"{site_url}/api/resource/Supplier/{name_key}"
    payload = {"supplier_name": supplier_name}
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)

    if resp.status_code == 404:
        existing = _find_existing_supplier(site_url, api_key, api_secret, supplier_name)
        if existing:
            name_key = quote(existing, safe="")
            put_url = f"{site_url}/api/resource/Supplier/{name_key}"
            resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)

    if resp.status_code == 404:
        post_url = f"{site_url}/api/resource/Supplier"
        resp = _request_with_token("POST", post_url, api_key, api_secret, payload)

    return (resp.ok, (resp.json() if resp.ok else resp.text))

def _upsert_price_list(site_url: str, api_key: str, api_secret: str, price_list_name: str, currency: str | None):
    """Ensure Price List exists on target with given currency."""
    if not price_list_name:
        return True, None
    name_key = quote(price_list_name, safe="")
    put_url = f"{site_url}/api/resource/Price%20List/{name_key}"
    payload = {
        "price_list_name": price_list_name,
        "currency": currency or "",
        "buying": 1,
        "selling": 0,
        "enabled": 1,
    }
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
    if resp.status_code == 404:
        post_url = f"{site_url}/api/resource/Price%20List"
        resp = _request_with_token("POST", post_url, api_key, api_secret, payload)
    return (resp.ok, (resp.json() if resp.ok else resp.text))

def _find_existing_item_price(site_url: str, api_key: str, api_secret: str, item_code: str, price_list: str, supplier: str | None, currency: str | None):
    """Lookup Item Price by unique tuple on target."""
    filters = [
        ["Item Price", "item_code", "=", item_code],
        ["Item Price", "price_list", "=", price_list],
    ]
    if supplier:
        filters.append(["Item Price", "supplier", "=", supplier])
    if currency:
        filters.append(["Item Price", "currency", "=", currency])

    try:
        resp = requests.get(
            f"{site_url}/api/resource/Item%20Price",
            headers=_auth_headers(api_key, api_secret),
            params={
                "fields": '["name"]',
                "filters": json.dumps(filters),
                "limit_page_length": 1,
            },
            timeout=20,
        )
        if resp.ok:
            data = (resp.json() or {}).get("data") or []
            if data:
                return data[0].get("name")
    except Exception:
        pass
    return None

def _upsert_item_price(site_url: str, api_key: str, api_secret: str, doc: dict):
    """Upsert Item Price on target via search->PUT, else POST."""
    item_code = doc.get("item_code")
    price_list = doc.get("price_list")
    supplier = doc.get("supplier")
    currency = doc.get("currency")

    existing = _find_existing_item_price(site_url, api_key, api_secret, item_code, price_list, supplier, currency)
    if existing:
        name_key = quote(existing, safe="")
        put_url = f"{site_url}/api/resource/Item%20Price/{name_key}"
        resp = _request_with_token("PUT", put_url, api_key, api_secret, doc)
        return (resp.ok, (resp.json() if resp.ok else resp.text))

    post_url = f"{site_url}/api/resource/Item%20Price"
    resp = _request_with_token("POST", post_url, api_key, api_secret, doc)
    return (resp.ok, (resp.json() if resp.ok else resp.text))

def _set_supplier_price_list_remote(site_url: str, api_key: str, api_secret: str, supplier_name: str, price_list: str):
    """Set Supplier.price_list on target server."""
    if not supplier_name or not price_list:
        return True, None

    # Find remote Supplier docname (handle naming differences)
    remote_name = _find_existing_supplier(site_url, api_key, api_secret, supplier_name)
    if not remote_name:
        ok, _ = _ensure_supplier_remote(site_url, api_key, api_secret, supplier_name)
        if not ok:
            return False, f"Supplier '{supplier_name}' not found and could not be created"
        remote_name = _find_existing_supplier(site_url, api_key, api_secret, supplier_name)
        if not remote_name:
            return False, f"Supplier '{supplier_name}' still not found after creation"

    name_key = quote(remote_name, safe="")
    put_url = f"{site_url}/api/resource/Supplier/{name_key}"
    payload = {"default_price_list": price_list}
    resp = _request_with_token("PUT", put_url, api_key, api_secret, payload)
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
def sync_item_prices_to_servers(sync_mode: str = "all", currency: str | None = None, run_in_background: int = 1):
    """
    Sync Item Prices linked to Suppliers to remote servers.
    - sync_mode: "all" or "currency"
    - currency: required when sync_mode == "currency"
    Returns standardized status: {status, message, synced, servers, details}
    """
    if cint(run_in_background):
        job = frappe.enqueue(
            "impex.impex.api.item_price_sync.sync_item_prices_to_servers",
            queue="long",
            timeout=10800,
            job_name=f"Sync Item Prices ({frappe.session.user})",
            sync_mode=sync_mode,
            currency=currency,
            run_in_background=0
        )
        return {
            "status": "queued",
            "message": "Item Price sync has been queued on the long worker.",
            "job_id": getattr(job, "id", None),
            "queue": "long"
        }

    sync_mode = (sync_mode or "all").lower()
    if sync_mode not in ("all", "currency"):
        return {"status": "failed", "message": "Invalid sync_mode. Use 'all' or 'currency'.", "synced": 0, "servers": 0, "details": []}
    if sync_mode == "currency" and not currency:
        return {"status": "failed", "message": "Currency is required when syncing by currency.", "synced": 0, "servers": 0, "details": []}

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

    # Collect Suppliers that have a Price List set
    suppliers = frappe.get_all(
        "Supplier",
        filters={"default_price_list": ["!=", ""], "disabled": 0},
        fields=["name", "supplier_name", "default_price_list"],
        limit=0,
    )
    if not suppliers:
        return {
            "status": "synced",
            "message": "No Suppliers with a Price List set.",
            "synced": 0,
            "servers": len(rows),
            "details": []
        }

    # Build the set of relevant Price Lists from Supplier.price_list
    price_lists = sorted({s.get("default_price_list") for s in suppliers if s.get("default_price_list")})

    # Collect Item Prices belonging to those Price Lists (supplier price lists, i.e. buying)
    ip_filters = {
        "selling": 0,
        "price_list": ["in", price_lists],
    }
    if sync_mode == "currency":
        ip_filters["currency"] = currency

    item_prices = frappe.get_all(
        "Item Price",
        filters=ip_filters,
        fields=[
            "name",
            "item_code",
            "price_list",
            "price_list_rate",
            "currency",
            "uom",
            "supplier",
        ],
        limit=0,
    )

    if not item_prices:
        return {
            "status": "synced",
            "message": "No Item Prices found for Suppliers' Price Lists with selected condition.",
            "synced": 0,
            "servers": len(rows),
            "details": []
        }

    # Map each Price List to a currency (prefer currency from its item prices; fallback to selected currency)
    pl_currency_map = {}
    for pl in price_lists:
        sample = next((ip for ip in item_prices if ip.get("price_list") == pl and ip.get("currency")), None)
        pl_currency_map[pl] = sample.get("currency") if sample else (currency if sync_mode == "currency" else None)

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

        if getattr(s, "disabled", 0):
            server_results.append({"site_url": s.site_url, "sent": 0, "errors": ["Disabled URL"]})
            continue

        sent = 0
        errors = []

        # Ensure all Price Lists exist on target first
        for pl in price_lists:
            ok, resp_msg = _upsert_price_list(site_url, api_key, api_secret, pl, pl_currency_map.get(pl))
            if not ok:
                errors.append(f"Price List '{pl}': {resp_msg}")

        # Ensure Suppliers exist and are linked to their Price List on target
        for sup in suppliers:
            sup_name = sup.get("supplier_name") or sup.get("name")
            pl = sup.get("default_price_list")
            ok, resp_msg = _ensure_supplier_remote(site_url, api_key, api_secret, sup_name)
            if not ok:
                errors.append(f"Supplier '{sup_name}': {resp_msg}")
                continue
            ok, resp_msg = _set_supplier_price_list_remote(site_url, api_key, api_secret, sup_name, pl)
            if not ok:
                errors.append(f"Supplier '{sup_name}' Price List link: {resp_msg}")

        # Sync each Item Price that belongs to those Price Lists
        for ip in item_prices:
            try:
                doc = {
                    "item_code": ip.get("item_code"),
                    "price_list": ip.get("price_list"),
                    "price_list_rate": ip.get("price_list_rate"),
                    "currency": ip.get("currency"),
                    "uom": ip.get("uom") or None,
                    "supplier": ip.get("supplier") or None,
                    "selling": 0,
                    "buying": 1,
                }

                ok, resp_msg = _upsert_item_price(site_url, api_key, api_secret, doc)
                if ok:
                    sent += 1
                else:
                    errors.append(f"Item Price [{ip.get('item_code')} @ {ip.get('price_list')}]: {resp_msg}")
            except Exception as e:
                errors.append(f"Item Price [{ip.get('item_code')} @ {ip.get('price_list')}]: {e}")

        last_sync_ts = now_datetime()
        try:
            _ensure_db_connection()
            frappe.db.set_value(
                "Item Sync Settings",
                s.name,
                "last_sync",
                last_sync_ts,
                update_modified=False
            )
            frappe.db.commit()
        except OperationalError:
            # Reconnect and retry once
            try:
                frappe.db.close()
            except Exception:
                pass
            frappe.db.connect()
            frappe.db.set_value(
                "Item Sync Settings",
                s.name,
                "last_sync",
                last_sync_ts,
                update_modified=False
            )
            frappe.db.commit()
        except Exception as e:
            errors.append(f"Failed to update last_sync: {e}")

        total_sent += sent
        server_results.append({"site_url": s.site_url, "sent": sent, "errors": errors})

    error_servers = sum(1 for r in server_results if r.get("errors"))
    status = "synced" if not (total_sent == 0 and error_servers == len(rows)) else "failed"
    message = f"Servers: {len(rows)}, Item Prices sent: {total_sent}. " + (f"{error_servers} server(s) had errors." if error_servers else "All servers OK.")

    try:
        all_errors = []
        for res in server_results:
            for err in (res.get("errors") or []):
                all_errors.append(f"[{res.get('site_url') or 'unknown'}] {err}")
        if all_errors:
            frappe.log_error("\n".join(all_errors), "Item Price Sync Errors")
    except Exception:
        pass

    return {
        "status": status,
        "message": message,
        "synced": total_sent,
        "servers": len(rows),
        "details": server_results
    }