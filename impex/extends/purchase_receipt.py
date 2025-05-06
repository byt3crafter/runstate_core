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

def on_cancel(doc, method):
    # On cancel of Purchase Receipt, change receipt status of associated sales invoice
    if doc.custom_inter_company_invoice_reference:
        linked_invoice = frappe.get_doc(
            "Sales Invoice", doc.custom_inter_company_invoice_reference
        )
        if linked_invoice:
            linked_invoice.update({
                "custom_receipt_status": '',
                "custom_receipt_date": '',
                "custom_received_by": ''
            })
            linked_invoice.save(ignore_permissions=True)
            linked_invoice.notify_update()