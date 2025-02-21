import frappe

def delete_old_item_prices():
    # Fetch all Item Price records sorted by 'modified' in descending order.
    # This ensures that the first record encountered for an item is the latest updated.
    item_prices = frappe.get_all(
        "Item Price",
        fields=["name", "item_code", "modified"],
        order_by="modified desc"
    )
    
    seen_items = set()
    for ip in item_prices:
        # If we have already encountered an item, this record is older and should be deleted.
        if ip.item_code in seen_items:
            try:
                frappe.delete_doc("Item Price", ip.name, force=True)
                frappe.db.commit()  # commit after each deletion, or you can commit once at the end
                print(f"Deleted old price record: {ip.name} for item {ip.item_code}")
            except Exception as e:
                frappe.log_error(message=str(e), title="Error deleting Item Price record")
        else:
            # Mark this item as encountered.
            seen_items.add(ip.item_code)

# To run the script directly (for example, via bench console)
if __name__ == "__main__":
    delete_old_item_prices()