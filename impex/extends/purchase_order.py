import frappe
from frappe import _
from impex.impex.doctype.purchase_order_generator.purchase_order_generator import create_sales_order
from impex.impex.doctype.price_change.price_change import create_price_change_from_purchase_invoice

def validate(doc, method):
    set_part_number(doc)
    if doc.custom_create_sales_order:
        validate_inter_company(doc)
    
def validate_inter_company(doc):
    # Validate that the company has an assciated customer for inter-company purchases
    company_customer = frappe.db.get_value("Impex Company Settings", {"company": doc.company}, "company_customer")
    if not company_customer or company_customer is None or company_customer == "":
        frappe.throw(_(f"""Please setup a customer for the {doc.company} company in Impex Settings
                       to create inter-company Sales Order"""))


def on_submit(doc, method):
    add_part_number(doc)
    if doc.custom_create_sales_order:
    	create_sales_order([doc.name])

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

@frappe.whitelist()
def recreate_manual_price_change(docname, doctype="Purchase Order"):
    fieldname = "purchase_order"
    if doctype == "Purchase Invoice":
        fieldname = "purchase_invoice"
    
    existing = frappe.db.get_all("Price Change", filters={fieldname: docname}, fields=["name", "docstatus"])
    if existing and len(existing) > 0:
        for row in existing:
            if row.docstatus == 1:
                url = frappe.utils.get_url_to_form("Price Change", row.name)
                frappe.throw(f"""Error: Please cancel Price Change <a href='{url}'>{row.name}</a> first""")
            
            if row.docstatus == 0:
                frappe.delete_doc("Price Change", row.name)
    create_price_change_from_purchase_invoice(doctype=doctype, doc_name=docname)
    