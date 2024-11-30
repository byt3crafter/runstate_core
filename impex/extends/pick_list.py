import frappe


def validate(doc, method):
    set_bin_location(doc, method)


def set_bin_location(doc, method):
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
