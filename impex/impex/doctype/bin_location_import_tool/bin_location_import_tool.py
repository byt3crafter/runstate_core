# Copyright (c) 2025, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import os
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file, read_xls_file_from_attached_file
from frappe.utils import file_lock, now_datetime, get_url
from frappe.model.docstatus import DocStatus
from frappe import _, msgprint
import json

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

			bin = frappe.db.exists("Bin Location", {"location": row[4]})
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
			location_exists = frappe.db.exists("Bin Location Item", {"item_code": item_code})
			if location_exists:
				attached_bin = frappe.db.get_value("Bin Location Item", location_exists, "parent")
				if attached_bin == bin.name:
					continue
				else:
					frappe.db.delete("Bin Location Item", {"name": location_exists})
			
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
	
def queue_action(self, action, **kwargs):
	#Run an action in background
	from frappe.utils.background_jobs import enqueue

	if file_lock.lock_exists(self.get_signature()):
		frappe.throw(_('This document is currently queued for execution. Please try again'),
			title=_('Document Queued'))
	
	frappe.db.set_value(self.doctype, self.name, 'queue_status', 'Queued',  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queue_failed', 0,  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queue_comment', '',  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queued_date', now_datetime(),  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queued_by', frappe.session.user,  update_modified=False)
	self.lock()
	enqueue('impex.impex.doctype.bin_location_import_tool.bin_location_import_tool.execute_action', doctype=self.doctype, name=self.name,
		action=action, **kwargs)
	
def execute_action(doctype, name, action, **kwargs):
	"""Execute an action on a document (called by background worker)"""
	doc = frappe.get_doc(doctype, name)
	doc.unlock()
	try:
		getattr(doc, action)(**kwargs)
		frappe.db.set_value(doctype, name, "queue_status", "Completed", update_modified=False)
	except Exception:
		frappe.db.rollback()

		# add a comment (?)
		if frappe.local.message_log:
			msg = json.loads(frappe.local.message_log[-1]).get('message')
		else:
			msg = '<pre><code>' + frappe.get_traceback() + '</pre></code>'

		doc.add_comment('Comment', _('Action Failed') + '<br><br>' + msg)
		frappe.db.set_value(doctype, name, 'queue_failed', 1, update_modified=False)
		frappe.db.set_value(doctype, name, 'queue_status', "Failed", update_modified=False)
		frappe.db.set_value(doctype, name, 'queue_comment', msg, update_modified=False)
		doc.notify_update()

