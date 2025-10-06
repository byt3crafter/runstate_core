import frappe

def execute():
	default_company = frappe.db.get_value("Impex Settings", "Impex Settings", "main_company")
	if default_company:
		processed = 0
		rules = frappe.db.get_all("Rule Prices", pluck="name")
		for rule in rules:
			frappe.db.set_value("Rule Prices", rule, "company", default_company)
			processed += 1
			if processed == 50:
				frappe.db.commit()
				processed = 0
			frappe.db.commit()