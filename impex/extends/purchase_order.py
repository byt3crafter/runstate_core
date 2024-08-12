import frappe
from frappe import _


def validate(doc, method):
    set_part_number(doc)


def on_submit(doc, method):
    add_part_number(doc)


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


def add_part_number(doc):
    # Get all items from the Purchase Receipt
    items = doc.items

    # Get the supplier from the Purchase Receipt
    supplier = doc.supplier

    # Loop through all items in the Purchase Receipt
    for item in items:
        # Get the item code for the current item
        item_code = item.item_code

        # Check if the supplier is already associated with this item in the "Item Supplier" table
        supplier_item = frappe.db.get_value(
            "Item Supplier", {"parent": item_code, "supplier": supplier}, "name"
        )

        # If the supplier is not already associated with this item
        if not supplier_item:
            # Create a new supplier item entry
            supplier_item = frappe.get_doc(
                {
                    "doctype": "Item Supplier",
                    "parent": item_code,
                    "parenttype": "Item",
                    "parentfield": "supplier_items",
                    "supplier": supplier,
                    "supplier_part_no": item.custom_part_number,  # Use the custom part number
                }
            )
            # Insert the new entry into the "Item Supplier" table, bypassing permission checks
            supplier_item.insert(ignore_permissions=True)
        # else:
        #     # If the supplier is already associated with this item, retrieve the existing entry
        #     supplier_item = frappe.get_doc("Item Supplier", supplier_item)
        #     # Check if the custom part number has changed
        #     if supplier_item.supplier_part_no != item.custom_part_number:
        #         # Update the supplier part number
        #         supplier_item.supplier_part_no = item.custom_part_number
        #         # Save the updated entry, bypassing permission checks
        #         supplier_item.save(ignore_permissions=True)
