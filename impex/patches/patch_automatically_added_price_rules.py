import frappe
from impex.impex.doctype.price_change.price_change import add_auto_price_rules

def execute():
	rules = frappe.db.get_all("Impex Settings Automatic Rule", fields=["document"])
	for row in rules:
		docs = frappe.db.get_all(row.document, pluck="name")
		for docname in docs:
			add_auto_price_rules(row.document, docname)
