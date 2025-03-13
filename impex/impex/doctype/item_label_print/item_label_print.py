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
		fields=['item_code', 'item_name', 'custom_label_qty as label_qty', 'supplier_part_no'])
	return items