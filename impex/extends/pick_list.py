import frappe


def validate(doc, method):
    set_bin_location(doc, method)


def set_bin_location(doc, method):
    if doc.get("locations") and len(doc.locations) > 0:
        for item in doc.locations:
            if item.item_code and item.warehouse:
                item.custom_bin_location = frappe.get_cached_value(
                    "Bin Location",
                    {"item_code": item.item_code, "warehouse": item.warehouse},
                    "name",
                )
