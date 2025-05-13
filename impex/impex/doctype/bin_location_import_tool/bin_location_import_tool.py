# Copyright (c) 2025, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import os
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file, read_xls_file_from_attached_file
from frappe.model.docstatus import DocStatus
from frappe import _, msgprint
from impex.extends.utils import queue_action


class BinLocationImportTool(Document):
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
			queue_action(self, "submit", timeout=2000)
		else:
			super().save()

	def on_submit(self):
		file_content = self.check_file()
		self.add_bin_location(file_content)

	def read_file(self):
		file_path = self.excel_file
		extn = os.path.splitext(file_path)[1][1:]

		file_content = None

		file_name = frappe.db.get_value("File", {"file_url": file_path})
		if file_name:
			file = frappe.get_doc("File", file_name)
			file_content = file.get_content()

		return file_content, extn

	def validate(self):
		self.check_file()

	def check_file(self):
		file_content, extn = self.read_file()
		if extn == "xlsx":
			file_content = read_xlsx_file_from_attached_file(fcontent=file_content)
		elif extn == "xls":
			file_content = read_xls_file_from_attached_file(file_content)
		else:
			frappe.throw("Only xls and xlsx files are supported.")
		return file_content
	
	def add_bin_location(self, data):
		limit = 500
		start = 0
		while start < len(data):
			end = start + limit
			self._add_bin_location(data[start:end])
			start = end

	def _add_bin_location(self, data):
		for row in data:
			if row[0] == "Group(2)":
				continue

			if row[4] is None or row[4] == "":
				continue
			
			# If the entries are regggarded as float type, change them to int to remove the decimal point
			if isinstance(row[0], float):
				row[0] = int(row[0])
			if isinstance(row[1], float):
				row[1] = int(row[1])
			if isinstance(row[4], float):
				row[4] = int(row[4])

			item_code = f"{str(row[0])}-{str(row[1])}"

			item_exists = frappe.db.exists("Item", {"item_code": item_code})
			if not item_exists:
				self.log_error(item_code, f"Item code {item_code} not found")
				continue

			bin = frappe.db.exists("Bin Location", {"location": row[4], "warehouse": self.warehouse}, cache=True)
			#frappe.log_error("Bin exists", f"Location: {row[4]}, Warehouse: {self.warehouse}, Bin: {bin}")
			if bin:
				bin = frappe.get_doc("Bin Location", bin)
			else:
				location = row[4]
				bin = frappe.new_doc("Bin Location")
				bin.update({
					"location": location,
					"title": location,
					"warehouse": self.warehouse,
					"company": self.company
				})
				#bin.save(ignore_permissions=True)

			# If location exists, check if it's in the bin, if not, then delete it
			location_exists = frappe.db.sql("""
						SELECT
							bli.name, parent
						FROM
							`tabBin Location Item` AS bli
						LEFT JOIN
							`tabBin Location` AS bl ON bli.parent = bl.name
						WHERE
							bl.warehouse = %(warehouse)s AND bli.item_code = %(item_code)s
						""", {"warehouse": self.warehouse, "item_code": item_code}, as_dict=1)
			if location_exists and len(location_exists) > 0:
				for location in location_exists:
					frappe.db.delete("Bin Location Item", {"name": location.name})
				
			
			bin.append("items", {
				"item_code": item_code
			})
			bin.save(ignore_permissions=True)
			frappe.db.commit()


	def log_error(self, item_code, error):
		error_entry = {
			"item_code": item_code,
			"error": error
		}
		self.append("error_log", error_entry)
		self.save()
		frappe.db.commit()