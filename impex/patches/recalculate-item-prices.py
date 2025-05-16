import frappe

def execute():
	draft_pricechange = frappe.db.get_all("Price Change", {"docstatus": 0})
	for price_change in draft_pricechange:
		doc = frappe.get_doc("Price Change", price_change)
		po_status = None
		pi_status = None
		if doc.purchase_order:
			po_status = frappe.db.get_value("Purchase Order", doc.purchase_order, "docstatus")
		elif doc.purchase_invoice:
			pi_status = frappe.db.get_value("Purchase Invoice", doc.purchase_invoice, "docstatus")

		if po_status == 0 or pi_status == 0:
			doc.validate()
			doc.save(ignore_permissions=True)