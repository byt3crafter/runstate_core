import frappe
from impex.impex.doctype.price_change.price_change import (
    create_price_change_from_purchase_invoice,
)


def on_submit(doc, method):
    update_supplier_price_list(doc)
    create_price_change_from_purchase_invoice(doc)


def update_supplier_price_list(doc):
    # Ensure the buying_price_list field is set
    if doc.buying_price_list:
        for item in doc.items:
            # Check if the item exists in the Price List
            price_list_item_name = frappe.db.exists(
                "Item Price",
                {"item_code": item.item_code, "price_list": doc.buying_price_list},
            )

            if price_list_item_name:
                # Update the existing item price
                price_list_item = frappe.get_doc("Item Price", price_list_item_name)
                price_list_item.price_list_rate = item.rate
                price_list_item.save()
            else:
                # Create a new Item Price
                new_price_list_item = frappe.get_doc(
                    {
                        "doctype": "Item Price",
                        "price_list": doc.buying_price_list,
                        "item_code": item.item_code,
                        "price_list_rate": item.rate,
                    }
                )
                new_price_list_item.insert()
