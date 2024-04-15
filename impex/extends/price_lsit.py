import frappe


def update_supplier_price_list(doc, method):
    # Update the price list of the supplier if:
    # - The price list is not the default price list
    # - The doc has a supplier and price list and items child table
    # - the method is submit

    if (
        doc.get("supplier")
        and doc.get("buying_price_list")
        and doc.get("items")
        and method == "on_submit"
    ):
        supplier_default_price_list = frappe.get_cached_value(
            "Supplier", doc.get("supplier"), "default_price_list"
        )
        supplier_price_list = None
        if (
            doc.get("buying_price_list")
            and doc.get("buying_price_list") == supplier_default_price_list
        ):
            supplier_price_list = supplier_default_price_list
        else:
            return

        if not supplier_price_list:
            return

        updated_items = []
        for item in doc.get("items"):
            item_code = item.get("item_code")
            rate = item.get("rate")
            if item_code and rate:
                # check if the item price exists
                exist_item_price = frappe.get_all(
                    "Item Price",
                    filters={
                        "item_code": item_code,
                        "price_list": supplier_price_list,
                        "supplier": doc.get("supplier"),
                        "buying": 1,
                        "uom": item.get("uom"),
                        "price_list_rate": rate,
                    },
                )
                if len(exist_item_price) > 0:
                    continue
                updated_items.append(item_code)
                item_price = frappe.new_doc("Item Price")
                item_price.item_code = item_code
                item_price.uom = item.get("uom")
                item_price.supplier = doc.get("supplier")
                item_price.buying = 1
                item_price.price_list = supplier_price_list
                item_price.price_list_rate = rate
                item_price.valid_from = frappe.utils.now_datetime()
                item_price.reference = doc.name
                item_price.note = f"Item price auto created from {doc.doctype}: '{doc.name}' for supplier '{doc.supplier}'"

                item_price.insert(ignore_permissions=True)

        if len(updated_items) > 0:
            frappe.msgprint(
                f"Supplier price list updated for items: {', '.join(updated_items)}",
                alert=True,
            )
