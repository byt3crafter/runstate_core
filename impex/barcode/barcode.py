import frappe

# import barcode
# from barcode import Code128
# from barcode.writer import ImageWriter


@frappe.whitelist()
def generate_barcode(docname):
    item = frappe.get_doc("Item", docname)

    # if item already has a barcode, then return
    if len(item.barcodes) > 0:
        return

    # Use the item_code for the barcode generation
    bcode = item.item_code

    return bcode


# @frappe.whitelist()
# def print_barcode(bcode):
#     # Implementation for printing barcode
#     pass
