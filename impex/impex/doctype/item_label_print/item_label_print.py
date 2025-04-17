# Copyright (c) 2025, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ItemLabelPrint(Document):
	pass

@frappe.whitelist()
def get_pr_items(purchase_receipt):
	items = frappe.db.get_all('Purchase Receipt Item', 
		filters={'parent': purchase_receipt}, 
		fields=['item_code', 'item_name', 'custom_label_qty as label_qty', 'supplier_part_no', 'warehouse'])
	
	# items = frappe.db.sql("""
	# 				SELECT
	# 					item.item_code, item.item_name, item.custom_label_qty as label_qty, 
	# 					item.supplier_part_no, location.name AS bin_location
	# 				FROM
	# 					`tabPurchase Receipt Item` AS item
	# 				LEFT JOIN
	# 					`tabBin Location Item` AS location_item ON location_item.item_code = item.item_code
	# 				LEFT JOIN
	# 					`tabBin Location` AS location ON location.name = location_item.parent
	# 				WHERE
	# 					item.parent = %(purchase_receipt)s AND location.warehouse = item.warehouse
	# 				""", {"purchase_receipt": purchase_receipt}, as_dict=1)
	for item in items:
		location = frappe.db.sql("""
					SELECT
						location.name 
					FROM
						`tabBin Location Item` AS location_item
					LEFT JOIN
						`tabBin Location` AS location ON location.name = location_item.parent
					WHERE
						location_item.item_code = %(item_code)s AND location.warehouse = %(warehouse)s
					""", {"item_code": item.item_code, "warehouse": item.warehouse}, as_dict=1)
		if location and len(location) > 0:
			item["bin_location"] = location[0].name
	return items

@frappe.whitelist()
def get_bin_locations(doctype, txt, searchfield, start, page_len, filters):
	item_code = filters.get("item_code")
	return frappe.db.sql("""
				SELECT
					location.name
				FROM
					`tabBin Location Item` AS item
				LEFT JOIN
					`tabBin Location` AS location ON item.parent = location.name
				WHERE
					item.item_code = %(item_code)s
				""", {"item_code": item_code})