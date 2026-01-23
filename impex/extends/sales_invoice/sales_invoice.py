import frappe
from frappe.model.naming import getseries, parse_naming_series
from datetime import datetime
import time
#from frappe.database.database import QueryDeadlockError

def autoname(doc, method):
	if doc.is_pos:
		naming_series = f"SINV-DRAFT"
		doc.name = f"SINV-DRAFT-{getseries(naming_series, 4)}"
	else:
		naming_series = parse_naming_series(doc.naming_series, "Sales Invoice", doc)
		if doc.naming_series.endswith('#'):
			doc.name = naming_series
		else:
			doc.name = f"{naming_series}{getseries(naming_series, 4)}"

def on_submit(doc, method):
	# Impex Customization: Check to see if any of the items are frozen
	for item in doc.items:
		is_frozen = frappe.db.exists("Item Stock Freeze", 
							{"parent": item.item_code, "warehouse": item.warehouse})
		if is_frozen:
			frappe.throw(f"""Error: Item {item.item_code} is currently being reconciled. 
				No transaction can be made against it.""")

def rename_invoice(doc, max_retries=3):
	retry_count = 0
	while retry_count < max_retries:
		try:
			naming_series = parse_naming_series(doc.naming_series, "Sales Invoice", doc)
			old_name = doc.name
			if doc.naming_series.endswith('#'):
				doc.name = naming_series
			else:
				doc.name = f"{naming_series}{getseries(naming_series, 4)}"
			
			frappe.rename_doc("Sales Invoice", old_name, doc.name, force=True)
			return 
		except frappe.QueryDeadlockError:
			retry_count += 1
			if retry_count == max_retries:
				frappe.log_error(
					message=f"Failed to rename invoice {doc.name} after {max_retries} attempts",
					title="Invoice Rename Deadlock"
				)
				raise  # Re-raise the last deadlock error if all retries failed
				
			# Exponential backoff: 0.1s, 0.2s, 0.4s
			time.sleep(0.1 * (2 ** (retry_count - 1)))
			frappe.db.rollback()  # Rollback the transaction before retrying