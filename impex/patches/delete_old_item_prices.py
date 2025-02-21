import frappe

def delete_old_item_prices():
    # Fetch all Item Price records sorted by 'modified' in descending order.
    # This ensures that the first record encountered for an item is the latest updated.
    item_prices = frappe.get_all(
        "Item Price",
        fields=["name", "item_code", "price_list", "modified"],
        order_by="modified desc"
    )
    
    seen_items = set()
    for ip in item_prices:
        # Create a unique key based on item_code and price_list
        item_key = (ip.item_code, ip.price_list)
        
        # If we have already encountered an item with the same price_list, this record is older and should be deleted.
        if item_key in seen_items:
            try:
                frappe.delete_doc("Item Price", ip.name, force=True)
                frappe.db.commit()  # commit after each deletion, or you can commit once at the end
                print(f"Deleted old price record: {ip.name} for item {ip.item_code} in price list {ip.price_list}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error deleting Item Price record")
        else:
            # Mark this item and price_list as encountered.
            seen_items.add(item_key)