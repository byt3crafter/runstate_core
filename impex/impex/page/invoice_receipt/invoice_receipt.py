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
			si.docstatus = 1 AND si.customer = %(customer)s AND 
			(si.custom_receipt_status IS NULL OR si.custom_receipt_status = '')
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
		doc = frappe.get_doc("Sales Invoice", invoice)

		purchase_orders = {}
		delivery_note_items = get_delivery_note_items(doc)
		frappe.log_error(title="Test", message=str(delivery_note_items))


		for row in doc.items:
			if row.custom_branch_purchase_order and row.custom_branch_purchase_order not in purchase_orders:
				purchase_orders[row.custom_branch_purchase_order] = set()
			purchase_orders[row.custom_branch_purchase_order].add(
				(row.item_code, row.custom_branch_purchase_order_item, row.qty, row.name)
			)

		for po, items in purchase_orders.items():
			purchase_order = frappe.get_doc("Purchase Order", po)
			first_key = next(iter(delivery_note_items))
			receipt_doc = frappe.get_doc({
					"doctype": "Purchase Receipt",
					"company": purchase_order.company,
					"supplier": purchase_order.supplier,
					"posting_date": current_datetime,
					"inter_company_reference": delivery_note_items[first_key]['parent']
				})

			for item_code, po_item, qty, name in items:
				receipt_doc.append("items", {
					"item_code": item_code,
					"qty": qty,
					"purchase_order": po,
					"purchase_order_item": po_item,
					"delivery_note_item": delivery_note_items[name]['name'],
					"from_warehouse": doc.items[0].warehouse,
					"warehouse": purchase_order.items[0].warehouse
				})
			receipt_doc.insert()
			receipt_doc.submit()

		frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_status", "Received")
		frappe.db.set_value("Sales Invoice", invoice, "custom_received_by", current_user)
		frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_date", current_datetime)

	frappe.db.commit()
	return "OK"

def get_delivery_note_items(invoice):
	delivery_note_items = {}
	undelivered_items = []

	for item in invoice.items:
		if item.delivery_note and item.dn_detail:
			dn_item = frappe._dict({"name": item.dn_detail, "parent": item.delivery_note})
		else:
			dn_item = frappe.db.get_value("Delivery Note Item", {"against_sales_invoice": invoice.name, "si_detail": item.name}, ["name", "parent"], as_dict=True)

		if not dn_item:
			undelivered_items.append(item)
		else:
			delivery_note_items[item.name] = dn_item

	if undelivered_items:
		delivery_note = frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": invoice.customer,
			"posting_date": now_datetime(),
			"items": [{
				"item_code": item.item_code,
				"qty": item.qty,
				"against_sales_invoice": invoice.name,
				"si_detail": item.name
			} for item in undelivered_items]
		})
		delivery_note.insert()
		delivery_note.submit()
		for item in delivery_note.items:
			delivery_note_items[item.si_detail] = {"name": item.name, "parent": delivery_note.name}

	return delivery_note_items

def get_delivery_notes(invoice):
	delivery_notes = []
	for item in invoice.items:
		if item.delivery_note and item.delivery_note is not None:
			dn = item.delivery_note
			delivery_note = frappe.get_doc("Delivery Note", dn)
			continue

		dn_exists = frappe.db.exists("Delivery Note Item", {"against_sales_invoice": invoice.name, "si_detail": item.name})
		if dn_exists:
			dn = frappe.db.get_value("Delivery Note Item", dn_exists, "parent")
			delivery_note = frappe.get_doc("Delivery Note", dn)
			delivery_notes.append(delivery_note)

		

	if len(delivery_notes) == 0:
		delivery_note= frappe.get_doc({
			"doctype": "Delivery Note",
			"customer": invoice.customer,
			"posting_date": now_datetime(),
			"items": [{
				"item_code": item.item_code,
				"qty": item.qty,
				"against_sales_invoice": invoice,
				"si_detail": item.name
			} for item in invoice.items]
		})
		delivery_note.insert()
		delivery_note.submit()
		delivery_notes.append(delivery_note)
	return delivery_notes