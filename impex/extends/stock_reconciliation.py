import frappe
from erpnext.stock.doctype.stock_reconciliation.stock_reconciliation import (
	get_item_and_warehouses, get_itemwise_batch, get_item_data, StockReconciliation)
from erpnext.stock.utils import get_stock_balance
from frappe.utils import cint

class CustomStockReconciliation(StockReconciliation):
	def validate(self):
		if not self.expense_account:
			self.expense_account = frappe.get_cached_value(
				"Company", self.company, "stock_adjustment_account"
			)
		if not self.cost_center:
			self.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
		self.validate_posting_time()
		
		# Impex Customization: Only remove items with no change if it is being submitted or 
		# if the custom checkmark has been checked
		if self.custom_remove_items_with_no_change or self._action == "submit":
			self.remove_items_with_no_change()

		self.validate_data()
		self.validate_expense_account()
		self.validate_customer_provided_item()
		self.set_zero_value_for_customer_provided_items()
		self.clean_serial_nos()
		self.set_total_qty_and_amount()
		self.validate_putaway_capacity()
		self.validate_inventory_dimension()

		if self._action == "submit":
			self.make_batches("warehouse")

	def on_update(self):
		frappe.msgprint("In here 1")
		if self._action != "submit":
			frappe.msgprint("In here 2")
			self.freeze_stock()

	def on_submit(self):
		super().on_submit()
		self.unfreeze_stock()

	def freeze_stock(self):
		frozen_stock = []
		for row in self.items:
			freeze_exists = frappe.db.exists("Item Stock Freeze", 
					{"warehouse": row.warehouse, "stock_reconciliation": self.name, "parent": row.item_code})
			if not freeze_exists:
				item = frappe.get_doc("Item", row.item_code)
				item.append("custom_stock_frozen_for_warehouse", {
					"warehouse": row.warehouse,
					"stock_reconciliation": self.name
				})
				item.save(ignore_permissions=True)

			frozen_stock.append(row.item_code)

		# Get previously frozen stock that has been removed from the stock reconciliation
		previous_frozen_stock = frappe.db.get_all("Item Stock Freeze", {"stock_reconciliation": self.name}, ["parent", "name"])
		for item in previous_frozen_stock:
			if item.parent not in frozen_stock:
				frappe.db.delete("Item Stock Freeze", item.name)

	def unfreeze_stock(self):
		frozen_stock = frappe.db.get_all("Item Stock Freeze", {"stock_reconciliation": self.name}, "name")
		for item in frozen_stock:
			frappe.db.delete("Item Stock Freeze", item.name)


@frappe.whitelist()
def get_items(warehouse, posting_date, posting_time, company, item_code=None, ignore_empty_stock=False, item_group=None):
	ignore_empty_stock = cint(ignore_empty_stock)
	items = []
	if item_code and warehouse:
		items = get_item_and_warehouses(item_code, warehouse)

	if not item_code:
		items = get_items_for_stock_reco(warehouse, item_group, company)

	res = []
	itemwise_batch_data = get_itemwise_batch(warehouse, posting_date, company, item_code)

	for d in items:
		if d.item_code in itemwise_batch_data:
			valuation_rate = get_stock_balance(
				d.item_code, d.warehouse, posting_date, posting_time, with_valuation_rate=True
			)[1]

			for row in itemwise_batch_data.get(d.item_code):
				if ignore_empty_stock and not row.qty:
					continue

				args = get_item_data(row, row.qty, valuation_rate)
				res.append(args)
		else:
			stock_bal = get_stock_balance(
				d.item_code,
				d.warehouse,
				posting_date,
				posting_time,
				with_valuation_rate=True,
				with_serial_no=cint(d.has_serial_no),
			)
			qty, valuation_rate, serial_no = (
				stock_bal[0],
				stock_bal[1],
				stock_bal[2] if cint(d.has_serial_no) else "",
			)

			if ignore_empty_stock and not stock_bal[0]:
				continue

			args = get_item_data(d, qty, valuation_rate, serial_no)

			res.append(args)

	return res

def get_items_for_stock_reco(warehouse, item_group, company):
	lft, rgt = frappe.db.get_value("Warehouse", warehouse, ["lft", "rgt"])

	item_group_condition = "and i.item_group = %(item_group)s" if item_group else ""
	params = {"lft": lft, "rgt": rgt, "company": company, "item_group": item_group}

	items = frappe.db.sql(
		f"""
		select
			i.name as item_code, i.item_name, bin.warehouse as warehouse, i.has_serial_no, i.has_batch_no
		from
			`tabBin` bin, `tabItem` i
		where
			i.name = bin.item_code
			and IFNULL(i.disabled, 0) = 0
			and i.is_stock_item = 1
			and i.has_variants = 0
			{item_group_condition}
			and exists(
				select name from `tabWarehouse` where lft >= %(lft)s and rgt <= %(rgt)s and name = bin.warehouse and is_group = 0
			)
	""",
		params,
		as_dict=1,
	)

	items += frappe.db.sql(
		f"""
		select
			i.name as item_code, i.item_name, id.default_warehouse as warehouse, i.has_serial_no, i.has_batch_no
		from
			`tabItem` i, `tabItem Default` id
		where
			i.name = id.parent
			and exists(
				select name from `tabWarehouse` where lft >= %(lft)s and rgt <= %(rgt)s and name=id.default_warehouse and is_group = 0
			)
			and i.is_stock_item = 1
			and i.has_variants = 0
			and IFNULL(i.disabled, 0) = 0
			{item_group_condition}
			and id.company = %(company)s
		group by i.name
	""",
		params,
		as_dict=1,
	)

	# remove duplicates
	# check if item-warehouse key extracted from each entry exists in set iw_keys
	# and update iw_keys
	iw_keys = set()
	items = [
		item
		for item in items
		if [
			(item.item_code, item.warehouse) not in iw_keys,
			iw_keys.add((item.item_code, item.warehouse)),
		][0]
	]

	return items