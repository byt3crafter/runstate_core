# Copyright (c) 2025, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file, read_xls_file_from_attached_file
import os
from frappe import _, msgprint
from frappe.model.docstatus import DocStatus
from impex.extends.utils import queue_action

class ItemPriceRuleImportTool(Document):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.current_item = ""  # Initialize as an instance variable
		self.current_item_doc = None

	def save(self):
		if self.docstatus == DocStatus.submitted() and \
			self.queue_status and self.queue_status != "Queued":
			msgprint(
				_(
					"The task has been enqueued as a background job. In case there is \
					any issue on processing in background, the system will add a comment \
					about the error on this document and revert to the Draft stage"
				)
			)
			queue_action(self, "submit", queue="long", timeout=7200)
		else:
			super().save()

	def on_submit(self):
		file_content = self.check_file()
		self.add_item_price_rule(file_content)

	def validate(self):
		self.check_file()

	def add_item_price_rule(self, data):
		limit = 100
		start = 0
		while start < len(data):
			end = start + limit
			self._add_item_price_rule(data[start:end])
			start = end
		frappe.db.commit()

	def _add_item_price_rule(self, data):
		for row in data:
			if row[0] == "Item Code" or row[0] == "":
				continue

			if self.current_item != row[0]:
				# Save the current item and load the next item
				if self.current_item_doc is not None:
					self.current_item_doc.save(ignore_permissions=True)
					frappe.db.commit()
					self.current_item_doc = None

				if frappe.db.exists("Item", {"item_code": row[0]}):
					self.current_item = row[0]
					self.current_item_doc = frappe.get_doc("Item", row[0])
					self.current_item_doc.rule_prices = []
				else:
					self.log_error(row[0], f"Item code {row[0]} not found")
					continue

			if self.current_item_doc is not None:
				self.current_item_doc.append("rule_prices", {
					"price_list": row[1],
					"margin": row[3],
					"base_price_list": row[2]
				})

			# if frappe.db.exists("Item", {"item_code": row[0]}):
			# 	self.current_item_doc = frappe.get_doc("Item", row[0])  # Use instance variable

			# 	if self.current_item != self.current_item_doc.item_code:
			# 		self.current_item = self.current_item_doc.item_code
			# 		self.current_item_doc.rule_prices = []

			# 	self.current_item_doc.append("rule_prices", {
			# 		"price_list": row[1],
			# 		"margin": row[3],
			# 		"base_price_list": row[2]
			# 	})
			# 	self.current_item_doc.save(ignore_permissions=True)
			# 	frappe.db.commit()
			# else:
			# 	self.log_error(row[0], f"Item code {row[0]} not found")
			# 	continue

	def check_file(self):
		file_content, extn = self.read_file()
		if extn == "xlsx":
			file_content = read_xlsx_file_from_attached_file(fcontent=file_content)
		elif extn == "xls":
			file_content = read_xls_file_from_attached_file(file_content)
		else:
			frappe.throw("Only xls and xlsx files are supported.")
		return file_content
	
	def read_file(self):
		file_path = self.excel_file
		extn = os.path.splitext(file_path)[1][1:]

		file_content = None

		file_name = frappe.db.get_value("File", {"file_url": file_path})
		if file_name:
			file = frappe.get_doc("File", file_name)
			file_content = file.get_content()

		return file_content, extn
	
	def log_error(self, item_code, error):
		error_entry = {
			"item_code": item_code,
			"error": error
		}
		self.append("error_log", error_entry)
		self.save()
		frappe.db.commit()
