import frappe
from frappe.utils import now_datetime
import json

@frappe.whitelist()
def get_invoices(company):
	customer = ""
	customer_exists = frappe.db.exists("Impex Company Settings", {"company": company})
	if customer_exists:
		customer = frappe.db.get_value("Impex Company Settings", customer_exists, "company_customer")
	else:
		frappe.throw(f"Error: The company {company} has not been setup for this function in Impex Settings. \
			   Please contact your administrator.")
	query = """
		SELECT 
			si.name AS invoice_name, sii.item_code, sii.item_name, 
			sii.qty, si.posting_date AS invoice_date
		FROM 
			`tabSales Invoice` si
		INNER JOIN 
			`tabSales Invoice Item` sii ON si.name = sii.parent
		WHERE 
			si.customer = %(customer)s AND (si.custom_receipt_status IS NULL OR si.custom_receipt_status = '')
			AND (sii.custom_branch_purchase_order IS NOT NULL AND sii.custom_branch_purchase_order != '')
	"""
	items = frappe.db.sql(query, {"customer": customer}, as_dict=True)
	print("Items: ", items)
	invoice_items = {}
	invoices = []

	# order returned data in invoices with invoice name and data and a dict with 
	# invoice name and list of items
	for item in items:
		invoice_name = item.pop('invoice_name')
		invoice_date = item.pop('invoice_date')
		row = {"name": invoice_name, "date": invoice_date}
		if row not in invoices:
			invoices.append(row)

		if invoice_name not in invoice_items:
			invoice_items[invoice_name] = []
		invoice_items[invoice_name].append(item)
	return {"invoices": invoices, "items": invoice_items}

@frappe.whitelist()
def confirm_receipt(invoices):
	if isinstance(invoices, str):
		invoices = json.loads(invoices)
	current_user = frappe.session.user
	current_datetime = now_datetime()

	for invoice in invoices:
		frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_status", "Received")
		frappe.db.set_value("Sales Invoice", invoice, "custom_received_by", current_user)
		frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_date", current_datetime)

	frappe.db.commit()
	return "OK"