# Copyright (c) 2024, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BinLocation(Document):
	def autoname(self):
		"""Set name as warehouse-location"""
		if self.warehouse and self.location:
			warehouse_name = frappe.db.get_value("Warehouse", self.warehouse, "warehouse_name")
			self.name = f"{self.location} - {warehouse_name}"
		else:
			frappe.throw("Warehouse and Location are required for naming the Bin Location")
