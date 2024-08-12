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
                    "parenttype": "Item",
                    "parentfield": "supplier_items",
                },
                fields=["name", "supplier_part_no"],
                ignore_permissions=True,
            )
            if sup_parts:
                for sup_part in sup_parts:
                    if item.custom_part_number != sup_part.supplier_part_no:
                        frappe.throw(
                            _(
                                f"Custom Part Number {item.custom_part_number} does not match the Supplier Part Number {sup_part.supplier_part_no} for Item {item.item_code}"
                            )
                        )
