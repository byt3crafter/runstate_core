import frappe
from impex.impex.doctype.price_change.price_change import add_auto_price_rules


def execute():
    item_groups = frappe.get_all("Item Group", pluck="name")
    if not item_groups:
        return
    
    processed = 0
    for name in item_groups:
        try:
            add_auto_price_rules("Item Group", name)
            processed += 1
            # Commit periodically to avoid long-running transaction
            if processed % 50 == 0:
                frappe.db.commit()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to add auto price rules for Item Group: {name}"
            )

    frappe.db.commit()
    frappe.logger().info(f"[Patch] Finished applying automatic price rules to {processed} Item Groups")