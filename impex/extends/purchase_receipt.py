import frappe
from frappe import _


def on_submit(doc, method):
    validate_part_number(doc)


def validate_part_number(doc):
    for item in doc.items:
        if item.custom_part_number:
            sup_parts = frappe.get_all(
                "Item Supplier",
                filters={
                    "supplier": doc.supplier,
                    "parent": item.item_code,
                    "supplier_part_no": item.custom_part_number,
                    "parenttype": "Item",
                    "parentfield": "supplier_items",
                },
                fields=["name"],
                ignore_permissions=True,
            )
            if not sup_parts:
                frappe.throw(
                    _(
                        "Supplier Part Number {0} does is not associated with Item {1} at row {2}"
                    ).format(item.custom_part_number, item.item_code, item.idx)
                )
