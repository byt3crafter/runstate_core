import frappe

def execute():
	default_company = frappe.db.get_value("Impex Settings", "Impex Settings", "main_company")
	if default_company:
		processed = 0
		rules = frappe.db.get_all("Supplier Price Change Rule", pluck="name")
		for rule in rules:
			frappe.db.set_value("Supplier Price Change Rule", rule, "company", default_company)
			processed += 1
			if processed == 50:
				frappe.db.commit()
				processed = 0
			frappe.db.commit()