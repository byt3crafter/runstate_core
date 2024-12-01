import frappe

def execute():
    """
    Migrate item_code from Bin Location doctype to Bin Location Item doctype
    """
    # First reload the doctypes to ensure we have the latest schema
    frappe.reload_doc("impex", "doctype", "bin_location")
    frappe.reload_doc("impex", "doctype", "bin_location_item")
    
    # Get all Bin Locations with item_code
    bin_locations = frappe.db.sql("""
        SELECT name, item_code 
        FROM `tabBin Location` 
        WHERE item_code IS NOT NULL AND item_code != ''
    """, as_dict=1)
    
    # Create Bin Location Item entries
    for bin_loc in bin_locations:
        # Create child table entry
        doc = frappe.get_doc("Bin Location", bin_loc.name)
        doc.append("items", {
            "item_code": bin_loc.item_code,
        })
        doc.save()

