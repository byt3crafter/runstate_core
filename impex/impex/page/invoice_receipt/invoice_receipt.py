import frappe
from frappe.utils import now_datetime
import json
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

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
		INNER JOIN
			`tabPurchase Order` po ON po.name = sii.custom_branch_purchase_order
		WHERE 
			si.docstatus = 1 AND si.customer = %(customer)s AND 
			(si.custom_receipt_status IS NULL OR si.custom_receipt_status = '')
			AND (sii.custom_branch_purchase_order IS NOT NULL AND sii.custom_branch_purchase_order != '')
			AND po.status <> 'Closed'
	"""
	items = frappe.db.sql(query, {"customer": customer}, as_dict=True)
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

	# Add the quantity of items for each invoice
	for invoice in invoices:
		invoice.update({"item_qty": len(invoice_items.get(invoice["name"], []))})
	return {"invoices": invoices, "items": invoice_items}

@frappe.whitelist()
def confirm_receipt(invoices):
	if isinstance(invoices, str):
		invoices = json.loads(invoices)
	current_user = frappe.session.user
	current_datetime = now_datetime()
	successful_invoices = []

	for invoice in invoices:
		all_pos_received = True
		doc = frappe.get_doc("Sales Invoice", invoice)

		# Group Purchase Orders by supplier
		supplier_pos = {}
		delivery_note_items = get_delivery_note_items(doc)

		for row in doc.items:
			if row.custom_branch_purchase_order:
				po = frappe.get_doc("Purchase Order", row.custom_branch_purchase_order)
				supplier = po.supplier
				
				if supplier not in supplier_pos:
					supplier_pos[supplier] = {}
				
				if po.name not in supplier_pos[supplier]:
					supplier_pos[supplier][po.name] = set()
				
				supplier_pos[supplier][po.name].add(
					(row.item_code, row.custom_branch_purchase_order_item, row.qty, row.uom, row.name)
				)

		# Create one Purchase Receipt per supplier
		for supplier, purchase_orders in supplier_pos.items():
			# Get the first PO to create the receipt
			first_po = next(iter(purchase_orders))
			receipt_doc = make_purchase_receipt(first_po)
			first_po_doc = frappe.get_doc("Purchase Order", first_po)
			
			# Set the inter-company reference
			first_key = next(iter(delivery_note_items))
			receipt_doc.update({
				"custom_inter_company_invoice_reference": invoice
			})

			# Clear existing items
			receipt_doc.items = []

			# Add items from all POs for this supplier
			for po, items in purchase_orders.items():
				po_doc = frappe.get_doc("Purchase Order", po)
				for item_code, po_item, qty, uom, name in items:
					receipt_doc.append("items", {
						"item_code": item_code,
						"qty": qty,
						"uom": uom,
						"purchase_order": po,
						"purchase_order_item": po_item,
						"custom_delivery_note": delivery_note_items[name]['parent'],
						"delivery_note_item": delivery_note_items[name]['name'],
						"from_warehouse": doc.items[0].warehouse,
						"warehouse": po_doc.items[0].warehouse
					})
			
			try:
				receipt_doc.submit()
			except Exception as e:
				all_pos_received = False
				frappe.log_error(
					message=f"Error creating Purchase Receipt for Invoice {invoice}, Supplier {supplier}: {str(e)}", 
					title="Error in Purchase Receipt Creation"
				)
				frappe.msgprint(
					f"An error occurred while creating the Purchase Receipt for Invoice {invoice}, Supplier {supplier}. {e}"
				)
				break

		if all_pos_received:
			frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_status", "Received")
			frappe.db.set_value("Sales Invoice", invoice, "custom_received_by", current_user)
			frappe.db.set_value("Sales Invoice", invoice, "custom_receipt_date", current_datetime)
			frappe.db.commit()
			successful_invoices.append(invoice)
		else:
			frappe.db.rollback()
			
	return successful_invoices

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
			"company": invoice.company,
			"customer": invoice.customer,
			"posting_date": now_datetime(),
			"currency": invoice.currency,
			"selling_price_list": invoice.selling_price_list,
			"items": [{
				"item_code": item.item_code,
				"qty": item.qty,
				"rate": item.rate,
				"warehouse": item.warehouse,
				"cost_center": item.cost_center,
				"project": item.project,
				"against_sales_invoice": invoice.name,
				"si_detail": item.name,
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
