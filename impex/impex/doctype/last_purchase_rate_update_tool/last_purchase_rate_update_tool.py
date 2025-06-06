# Copyright (c) 2025, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LastPurchaseRateUpdateTool(Document):
	def on_submit(self):
		for row in self.items:
			if row.new_rate > 0:
				frappe.db.set_value("Item", row.item_code, "last_purchase_rate", row.new_rate)