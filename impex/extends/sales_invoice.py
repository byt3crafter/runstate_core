import frappe
from frappe.model.naming import getseries, parse_naming_series
from datetime import datetime

def autoname(doc, method):
	naming_series = f"SINV-DRAFT"
	doc.name = f"SINV-DRAFT-{getseries(naming_series, 4)}"

def on_submit(doc, method):
	rename_invoice(doc)

def rename_invoice(doc):
	naming_series = parse_naming_series(doc.naming_series, "Sales Invoice", doc)
	old_name = doc.name
	if doc.naming_series.endswith('#'):
		doc.name = naming_series
	else:
		doc.name = f"{naming_series}{getseries(naming_series, 4)}"
	frappe.rename_doc("Sales Invoice", old_name, doc.name, force=True)