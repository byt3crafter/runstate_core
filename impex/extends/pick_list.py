import frappe


def validate(doc, method):
    set_bin_location(doc, method)
    sort_items(doc, method)


def set_bin_location(doc, method):
    """
    Set the bin location for each item
    """
    if doc.get("locations") and len(doc.locations) > 0:
        for item in doc.locations:
            if item.item_code and item.warehouse and not item.custom_bin_location:
                all_item_bins = frappe.db.sql(
                    """
                    SELECT BL.name 
                    FROM `tabBin Location` BL  
                    LEFT JOIN `tabBin Location Item` BLI on BL.name = BLI.parent
                    WHERE BL.warehouse=%s
                    AND BLI.item_code=%s
                    """,
                    (item.warehouse, item.item_code),
                )
                if all_item_bins:
                    item.custom_bin_location = all_item_bins[0][0]


def sort_items(doc, method):
    """
    Sort items by bin location in descending order
    """
    if doc.get("locations"):
        items_list = doc.locations
        doc.locations = []
        # Sort locations by custom_bin_location in descending order
        sorted_items = sorted(
            items_list,
            key=lambda x: (x.custom_bin_location or ""),
            reverse=True
        )
        
        # Reassign the sorted items to the doc.locations
        doc.locations = sorted_items
        