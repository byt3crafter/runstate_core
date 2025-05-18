import frappe
from erpnext.stock.utils import get_stock_balance
from erpnext.stock.stock_ledger import get_valuation_rate
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

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
	
@frappe.whitelist()
def get_item_details(item_code):
	item_name, item_group, description, image = frappe.db.get_value("Item", item_code, 
												["item_name", "item_group", "description", "image"])
	item = frappe.get_doc("Item", item_code)
	prices = frappe.get_all(
		"Item Price",
		filters={"item_code": item_code},
		fields=["price_list", "price_list_rate"],
	)

	# Get the last purchase supplier
	user_company = get_user_company()
	item_supplier = ""
	last_supplier = frappe.db.sql("""
					SELECT
						pr.supplier
					FROM
						`tabPurchase Invoice Item` AS pri
					LEFT JOIN
						`tabPurchase Invoice` AS pr ON pri.parent = pr.name
					WHERE
						pri.item_code = %(item_code)s AND pr.company = %(company)s
					ORDER BY
						pr.posting_date DESC
					LIMIT 1
					""", {"item_code": item_code, "company": user_company}, as_dict=1)
	if last_supplier and len(last_supplier) > 0:
		item_supplier = last_supplier[0].supplier

	# Get bin location based on company
	bin_location = ""
	if user_company:
		location = frappe.db.sql("""
						SELECT
							location.location
						FROM
							`tabBin Location Item` AS item
						LEFT JOIN
							`tabBin Location` AS location ON item.parent = location.name
						WHERE
							item.item_code = %(item_code)s AND location.company = %(user_company)s
						LIMIT 1
						""", {"item_code": item_code, "user_company": user_company}, as_dict=1)
		if len(location) > 0:
			bin_location = location[0].location

	cost = get_cost(item_code, user_company)

	return {
		"item_code": item_code,
		"item_name": item_name,
		"description": description,
		"item_group": item_group,
		"image": image,
		"supplier": item_supplier,
		"bin_location": bin_location,
		"total_sold": get_sold(item_code, user_company),
		"total_purchased": get_purchased(item_code, user_company),
		"current_stock": get_company_balance(item_code, user_company),
		"cost": cost,
		"selling_prices": get_selling_prices(item_code, user_company, cost),
		"company_details": get_company_item_details(item_code, user_company),
		"monthly_sales": get_monthly_sales(item_code, user_company),
		"monthly_purchases": get_monthly_purchases(item_code, user_company),
	}

def get_user_company():
	user = frappe.session.user

	user_company = frappe.defaults.get_user_default("Company")
	if not user_company:
		permission = frappe.db.exists("User Permission", {
			"user": user,
			"allow": "Company"
		})
		user_company = frappe.db.get_value("User Permission", permission, "for_value")

	user_company = frappe.defaults.get_user_default("Company")
	if not user_company:
		permission = frappe.db.exists("User Permission", {
			"user": user,
			"allow": "Company"
		})
		user_company = frappe.db.get_value("User Permission", permission, "for_value")
	
	if not user_company:
		user_company = frappe.db.get_single_value("Impex Settings", "main_company")

	return user_company

def get_sold(item_code, user_company):
	total_sold = 0
	sold = frappe.db.sql("""
				SELECT
					SUM(item.qty) AS total_qty
				FROM
					`tabSales Invoice Item` AS item
				LEFT JOIN
					`tabSales Invoice` AS invoice ON item.parent = invoice.name
				WHERE
					invoice.company = %(user_company)s AND item.item_code = %(item_code)s
				""", {"user_company": user_company, "item_code": item_code}, as_dict=1)
	if len(sold) > 0:
		total_sold = sold[0].total_qty
	return total_sold

def get_purchased(item_code, user_company):
	total_purchased = 0
	purchased = frappe.db.sql("""
					SELECT
						SUM(item.qty) AS total_qty
					FROM
						`tabPurchase Invoice Item` AS item
					LEFT JOIN
						`tabPurchase Invoice` AS invoice ON invoice.name = item.parent
					WHERE
						invoice.company = %(user_company)s AND item.item_code = %(item_code)s
					""", {"user_company": user_company, "item_code": item_code}, as_dict=1)
	if len(purchased) > 0:
		total_purchased = purchased[0].total_qty
	return total_purchased

def get_company_balance(item_code, user_company):
	# Get stock balance for all warehouses
	stock_balance = 0
	warehouses = frappe.db.get_all("Warehouse", filters={"company": user_company, "is_group": 0}, fields=["name"])
	for warehouse in warehouses:
		stock_balance += get_stock_balance(item_code, warehouse.name)
	return stock_balance

def get_cost(item_code, user_company):
	item_cost = 0

	price_list = frappe.db.get_single_value("Impex Settings", "item_details_buying_price_list")

	if price_list and price_list != "":
		buying_cost = frappe.db.get_value("Item Price", 
							{"item_code": item_code, "price_list": price_list}, "price_list_rate")
		if buying_cost and buying_cost != "":
			item_cost = buying_cost
	
	return item_cost

def get_selling_prices(item_code, user_company, cost=0):
	price_lists = []
	selling_prices = []

	# If it's main company then get all price lists 
	# otherwise get price lists from pos profiles
	main_company = frappe.db.get_single_value("Impex Settings", "main_company")
	if user_company == main_company:
		price_lists = frappe.db.get_all("Price List", {"enabled": 1, "selling": 1}, pluck="name")
	else:
		pls = frappe.db.get_all("POS Profile", filters={"company": user_company}, 
						  fields=["selling_price_list"])
		for pl in pls:
			if pl.selling_price_list and pl.selling_price_list != "" and pl.selling_price_list not in price_lists:
				price_lists.append(pl.selling_price_list)

	for price_list in price_lists:
		price = frappe.get_value("Item Price", filters={"item_code": item_code, "price_list": price_list}, fieldname="price_list_rate")
		if price:
			if cost > 0:
				percent_increase = ((price - cost) * 100) / cost
			else:
				percent_increase = 0

			selling_prices.append({
				"price_list": price_list,
				"price": round(price, 2),
				"percent_diff": round(percent_increase, 2)
			})
	return selling_prices

def get_company_item_details(item_code, user_company):
	companies = []
	main_company = frappe.db.get_single_value("Impex Settings", "main_company")
	# If it's the main company then get details for all companies, otherwise
	# only return details for the user-company
	if user_company == main_company:
		companies = frappe.db.get_all("Company", pluck="name")
	else:
		companies.append(user_company)

	companies_details = {}
	for company in companies:
		bo_sales = get_ordered(item_code, company) or 0
		bo_purchase = get_expected(item_code, company) or 0
		in_stock = get_company_balance(item_code, company)
		four_months_average = get_four_months_average(item_code, company)
		twelve_months_sales = get_twelve_months_sales(item_code, company)
		companies_details[company] = {
			"company": company,
			"bo_sales": bo_sales,
			"bo_purchase": bo_purchase,
			"in_stock": in_stock,
			"four_months_average": four_months_average,
			"twelve_months_sales": twelve_months_sales
		}
	return {"companies": companies, "companies_details": companies_details}

def get_expected(item_code, user_company):
	total_expected = 0
	expected = frappe.db.sql("""
					SELECT
						SUM(item.qty) AS total_qty
					FROM
						`tabPurchase Order Item` AS item
					LEFT JOIN
						`tabPurchase Order` AS po ON po.name = item.parent
					WHERE
						po.company = %(user_company)s AND item.item_code = %(item_code)s
					""", {"user_company": user_company, "item_code": item_code}, as_dict=1)
	if len(expected) > 0:
		total_expected = expected[0].total_qty
	return total_expected

def get_ordered(item_code, user_company):
	total_ordered = 0
	ordered = frappe.db.sql("""
					SELECT
						SUM(item.qty) AS total_qty
					FROM
						`tabSales Order Item` item
					LEFT JOIN
						`tabSales Order` so ON so.name = item.parent
					WHERE
						item.item_code = %(item_code)s AND so.company = %(user_company)s
					""", {"user_company": user_company, "item_code": item_code}, as_dict=1)
	if len(ordered) > 0:
		total_ordered = ordered[0].total_qty
	return total_ordered
	
def get_four_months_average(item_code, company):
	average_sales = 0
	total_sales = 0
	four_months_ago = datetime.now() - relativedelta(months=4)
	four_months_ago = four_months_ago.strftime("%Y-%m-%d")

	sales = frappe.db.sql("""
					SELECT
						SUM(item.qty) AS total_qty
					FROM
						`tabSales Invoice Item` AS item
					LEFT JOIN
						`tabSales Invoice` AS invoice ON item.parent = invoice.name
					WHERE
						invoice.company = %(company)s AND item.item_code = %(item_code)s
						AND invoice.posting_date >= %(start_date)s
					""", {"company": company, "item_code": item_code, "start_date": four_months_ago}, as_dict=1)
	if sales and len(sales) > 0:
		total_sales = sales[0].total_qty or 0
		average_sales = total_sales / 4

	return average_sales

def get_twelve_months_sales(item_code, company):
	total_sales = 0
	twelve_months_ago = datetime.now() - relativedelta(months=4)
	twelve_months_ago = twelve_months_ago.strftime("%Y-%m-%d")

	sales = frappe.db.sql("""
					SELECT
						SUM(item.qty) AS total_qty
					FROM
						`tabSales Invoice Item` AS item
					LEFT JOIN
						`tabSales Invoice` AS invoice ON item.parent = invoice.name
					WHERE
						invoice.company = %(company)s AND item.item_code = %(item_code)s
						AND invoice.posting_date >= %(start_date)s
					""", {"company": company, "item_code": item_code, "start_date": twelve_months_ago}, as_dict=1)
	if sales and len(sales) > 0:
		total_sales = sales[0].total_qty or 0

	return total_sales

def get_monthly_sales(item_code, company):
	monthly_sales = {}
	current_date = datetime.now()

	for i in range(12):
		start_date = (current_date - relativedelta(months=i+1)).replace(day=1).strftime("%Y-%m-%d")
		end_date = (current_date - relativedelta(months=i)).replace(day=1).strftime("%Y-%m-%d")

		sales = frappe.db.sql("""
						SELECT
							SUM(item.qty) AS total_qty
						FROM
							`tabSales Invoice Item` AS item
						LEFT JOIN
							`tabSales Invoice` AS invoice ON item.parent = invoice.name
						WHERE
							invoice.company = %(company)s AND item.item_code = %(item_code)s
							AND invoice.posting_date >= %(start_date)s AND invoice.posting_date < %(end_date)s
						""", {"company": company, "item_code": item_code, "start_date": start_date, "end_date": end_date}, as_dict=1)
		
		month = (current_date - relativedelta(months=i)).strftime("%m-%y")
		monthly_sales[month] = sales[0].total_qty if sales and sales[0].total_qty else 0

	return monthly_sales

def get_monthly_purchases(item_code, company):
	monthly_purchases = {}
	current_date = datetime.now()

	for i in range(12):
		start_date = (current_date - relativedelta(months=i+1)).replace(day=1).strftime("%Y-%m-%d")
		end_date = (current_date - relativedelta(months=i)).replace(day=1).strftime("%Y-%m-%d")

		purchases = frappe.db.sql("""
						SELECT
							SUM(item.qty) AS total_qty
						FROM
							`tabPurchase Invoice Item` AS item
						LEFT JOIN
							`tabPurchase Invoice` AS invoice ON item.parent = invoice.name
						WHERE
							invoice.company = %(company)s AND item.item_code = %(item_code)s
							AND invoice.posting_date >= %(start_date)s AND invoice.posting_date < %(end_date)s
						""", {"company": company, "item_code": item_code, "start_date": start_date, "end_date": end_date}, as_dict=1)
		
		month = (current_date - relativedelta(months=i)).strftime("%m-%y")
		monthly_purchases[month] = purchases[0].total_qty if purchases and purchases[0].total_qty else 0

	return monthly_purchases

@frappe.whitelist()
def get_cost_history(item_code, page=1, page_size=20):
	start = (int(page) - 1) * int(page_size)
	
	entries = frappe.db.sql("""
		SELECT 
			pi.rate as cost,
			pi.parent as doc,
			p.posting_date as date,
			p.supplier
		FROM 
			`tabPurchase Invoice Item` pi
		JOIN 
			`tabPurchase Invoice` p ON pi.parent = p.name
		WHERE 
			pi.item_code = %s
			AND p.docstatus = 1
		ORDER BY 
			p.posting_date DESC
		LIMIT %s OFFSET %s
	""", (item_code, int(page_size) + 1, start), as_dict=1)

	has_more = len(entries) > int(page_size)
	entries = entries[:int(page_size)]  # Remove the extra item we fetched

	# Add URL for each entry
	for entry in entries:
		entry['date'] = entry['date'].strftime('%d-%m-%Y')
		entry['doc_url'] = frappe.utils.get_url_to_form('Purchase Invoice', entry.doc)


	return {
		"entries": entries,
		"has_more": has_more
	}