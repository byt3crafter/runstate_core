import frappe
from frappe import _


def validate(doc, method):
    set_part_number(doc)


def set_part_number(doc):
    if not doc.supplier:
        return
    for item in doc.items:
        if item.item_code and not item.custom_part_number:
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
                item.custom_part_number = sup_parts[0].supplier_part_no
