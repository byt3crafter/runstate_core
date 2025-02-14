import frappe

@frappe.whitelist()
def get_bin_locations(item_code):
	user = frappe.session.user
	companies = frappe.get_all('User Permission', filters={
		'user': user,
		'allow': 'Company'
	}, fields=['for_value'])

	if not companies:
		company_clause = ""
	else:
		company_clause = "AND bl.company IN %(company_tuple)s"
	
	company_list = [company['for_value'] for company in companies]
	company_tuple = tuple(company_list)

	bin_locations = frappe.db.sql(f"""
								SELECT
									bl.warehouse, bl.location
								FROM
									`tabBin Location Item` AS bli
								LEFT JOIN
									`tabBin Location` AS  bl ON bli.parent = bl.name
								WHERE
									bli.item_code = %(item_code)s {company_clause}
							""", {"item_code": item_code, "company_tuple": company_tuple}, as_dict=1)
	return bin_locations

@frappe.whitelist()
def update_bin_location(item_code, warehouse, new_location):
	# If location exists, then delete it
	bin_location = frappe.db.sql("""
						SELECT
							bli.name
						FROM
							`tabBin Location Item` AS bli
						LEFT JOIN
							`tabBin Location` AS bl ON bli.parent = bl.name
						WHERE
							bl.warehouse = %(warehouse)s AND bli.item_code = %(item_code)s
						LIMIT 1
						""", {"warehouse": warehouse, "item_code": item_code}, as_dict=1)
	if bin_location and len(bin_location) > 0:
		frappe.db.delete("Bin Location Item", {"name": bin_location[0].name})

	bin_exists = frappe.db.exists("Bin Location", {"name": new_location})
	if bin_exists:
		doc = frappe.get_doc("Bin Location", new_location)
		if doc.warehouse != warehouse:
			frappe.throw(f"Error: The bin location you've selected does not \
				belong to the {warehouse} warehouse")
		doc.append("items", {
			"item_code": item_code
		})
		doc.save()
		return doc