# Copyright (c) 2024, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.setup.doctype.item_group.item_group import get_child_item_groups


class PurchaseOrderGenerator(Document):
    def validate(self):
        pass

    def on_submit(self):
        self.create_purchase_orders()

    def create_purchase_orders(self):
        # group items by supplier and create a purchase order for each supplier
        items = {}
        for item in self.items:
            if item.purchase_supplier not in items:
                items[item.purchase_supplier] = []
            items[item.purchase_supplier].append(item)

        for supplier in items:
            purchase_order = frappe.new_doc("Purchase Order")
            purchase_order.supplier = supplier
            purchase_order.company = self.company
            purchase_order.posting_date = self.date
            purchase_order.set("items", [])
            purchase_order.currency = items[supplier][0].purchase_currency
            for item in items[supplier]:
                purchase_order.append(
                    "items",
                    {
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "item_group": item.item_group,
                        "qty": item.purchase_qty,
                        "rate": item.purchase_rate,
                        "schedule_date": item.purchase_date,
                    },
                )
            purchase_order.save(ignore_permissions=True)
            purchase_order.reload()

            # set the purchase order name and item row in each item in the Purchase Order Generator Items table
            for item in items[supplier]:
                for purchase_order_item in purchase_order.items:
                    if item.item_code == purchase_order_item.item_code:
                        frappe.db.set_value(
                            "Purchase Order Generator Items",
                            item.name,
                            "poi",
                            purchase_order_item.name,
                        )
                        frappe.db.set_value(
                            "Purchase Order Generator Items",
                            item.name,
                            "po",
                            purchase_order.name,
                        )

            # show a message to the user that the purchase orders are created with a link to the purchase orders
            link = frappe.utils.get_url_to_form("Purchase Order", purchase_order.name)
            frappe.msgprint(
                f"""Purchase Order <a href="{link}">{purchase_order.name}</a>  is created for supplier {supplier}"""
            )

    @frappe.whitelist()
    def get_items(self):
        self.date = frappe.utils.today()
        items = []
        if (
            self.type == "Sales Orders"
        ):  # we need to get the items from the unfulfilled sales orders
            items = get_items_from_sales_orders(
                self.company, self.from_date, self.to_date, self.item_group
            )
            # set sales average and total for each item
            items = get_items_sales(
                self.company, self.from_date, self.to_date, self.item_group, items
            )
        elif self.type == "Historical Sales":
            items = get_items_sales(
                self.company, self.from_date, self.to_date, self.item_group
            )
            # set sales orders qty and base_net_amount for each item
            items = get_items_from_sales_orders(
                self.company, self.from_date, self.to_date, self.item_group, items
            )

        # set last purchase rate, qty, supplier, date for each item
        items = get_last_purchase_transactions_record(items, self.company)
        # set cheapest purchase rate, qty, supplier, date for each item
        items = get_cheapest_purchase_transactions_record(items, self.company)

        # set existing stock qty for each item
        items = get_existing_stock_qty(items, self.company)

        # set open purchase orders qty for each item
        items = get_open_purchase_orders_items(items, self.company)

        # update the items table
        self.items = []
        for item in items:
            item = frappe._dict(item)
            # set required purchase qty for each item
            self.set_required_purchase_qty(item)
            if item.purchase_qty > 0:
                self.append("items", item)

        return self.items

    def set_required_purchase_qty(self, item):
        # set required purchase qty for each item
        item.purchase_qty = (
            (item.sales_orders_qty or 0)
            + ((item.sales_average or 0) * int(self.months_required or 0))
            - (item.existing_qty or 0)
            - (item.open_purchase_qty or 0)
        )
        item.purchase_qty = int(item.purchase_qty)
        item.purchase_rate = item.cheapest_purchase_rate or item.last_purchase_rate
        item.purchase_supplier = (
            item.cheapest_purchase_supplier or item.last_purchase_supplier
        )
        item.purchase_date = frappe.utils.today()
        item.purchase_currency = (
            item.cheapest_purchase_currency or item.last_purchase_currency
        )


def get_items_from_sales_orders(
    company, from_date, to_date, item_group=None, items=None
):
    # return the items from the unfulfilled sales orders
    # fields: item_code, item_name, item_group, qty, base_net_amount
    conditions = f"""
        SO.docstatus = 1 
        AND SO.status IN ('To Deliver and Bill', 'To Deliver') 
        AND SO.company = '{company}' 
        AND SO.transaction_date BETWEEN '{from_date}' AND '{to_date}'
        AND SOI.qty > SOI.delivered_qty
        """
    if item_group:
        groups = get_child_item_groups(item_group)
        groups = tuple(groups)
        if len(groups) == 1:
            groups = f"""('{groups[0]}')"""
        conditions += f""" AND SOI.item_group IN {groups}"""

    if items and len(items) > 0:
        items_list = [item["item_code"] for item in items]
        items_list = tuple(items_list)
        if len(items_list) == 0:
            return items
        if len(items_list) == 1:
            items_list = f"""('{items_list[0]}')"""
        conditions += f""" AND SOI.item_code IN {items_list}"""

    items_data = frappe.db.sql(
        f"""SELECT item_code, item_name, item_group, SUM(qty) AS sales_orders_qty, SUM(base_net_amount) AS base_net_amount
        FROM `tabSales Order Item` SOI
        INNER JOIN `tabSales Order` SO ON SOI.parent = SO.name
        WHERE {conditions}
        GROUP BY item_code""",
        as_dict=True,
    )
    if items:
        # update only sales_orders_qty and base_net_amount and retrun the updated items
        for item in items:
            for item_data in items_data:
                if item["item_code"] == item_data["item_code"]:
                    item["sales_orders_qty"] = item_data["sales_orders_qty"]
                    item["base_net_amount"] = item_data["base_net_amount"]
        return items
    else:
        return items_data


def get_last_purchase_transactions_record(items, company):
    # return the last purchase transaction for each item
    # fields: date , qty, rate, amount, supplier
    for item in items:
        last_purchase_transaction = frappe.db.sql(
            f"""SELECT P.posting_date AS date, PI.qty, PI.rate, PI.amount, P.supplier, P.currency
                FROM `tabPurchase Invoice Item` PI
                INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                WHERE PI.item_code = '{item["item_code"]}' AND P.company = '{company}'
                ORDER BY P.posting_date DESC
                LIMIT 1""",
            as_dict=True,
        )
        if last_purchase_transaction:
            item["last_purchase_rate"] = last_purchase_transaction[0].rate
            item["last_purchase_supplier"] = last_purchase_transaction[0].supplier
            item["last_purchase_qty"] = last_purchase_transaction[0].qty
            item["last_purchase_date"] = last_purchase_transaction[0].date
            item["last_purchase_currency"] = last_purchase_transaction[0].currency

    return items


def get_cheapest_purchase_transactions_record(items, company):
    # return the cheapest purchase transaction for each item
    # fields: date , qty, rate, amount, supplier

    for item in items:
        cheapest_purchase_transaction = frappe.db.sql(
            f"""SELECT P.posting_date AS date, PI.qty, PI.rate, PI.amount, P.supplier, P.currency
                FROM `tabPurchase Invoice Item` PI
                INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                WHERE PI.item_code = '{item["item_code"]}' AND P.company = '{company}'
                ORDER BY PI.base_rate ASC
                LIMIT 1""",
            as_dict=True,
        )
        if cheapest_purchase_transaction:
            item["cheapest_purchase_rate"] = cheapest_purchase_transaction[0].rate
            item["cheapest_purchase_supplier"] = cheapest_purchase_transaction[
                0
            ].supplier
            item["cheapest_purchase_qty"] = cheapest_purchase_transaction[0].qty
            item["cheapest_purchase_date"] = cheapest_purchase_transaction[0].date
            item["cheapest_purchase_currency"] = cheapest_purchase_transaction[
                0
            ].currency

    return items


def get_existing_stock_qty(items, company):
    # return the existing stock qty for each item in the warehouse of the company
    # fields: qty
    warehouses = get_company_warehouses(company)
    items_list = [item["item_code"] for item in items]
    items_list = tuple(items_list)
    if len(items_list) == 0:
        return items
    if len(items_list) == 1:
        items_list = f"""('{items_list[0]}')"""
    if len(warehouses) == 0:
        return items
    if len(warehouses) == 1:
        warehouses = f"""('{warehouses[0]}')"""
    quantities = frappe.db.sql(
        f"""SELECT item_code, warehouse, SUM(actual_qty) AS qty
            FROM `tabBin`
            WHERE warehouse IN {warehouses} AND item_code IN {items_list}
            GROUP BY item_code, warehouse""",
        as_dict=True,
    )
    for item in items:
        for quantity in quantities:
            if item["item_code"] == quantity["item_code"]:
                item["existing_qty"] = quantity["qty"]

    return items


def get_company_warehouses(company):
    # return a tuple of all warehouses of the company if they are not a group
    # fields: name
    warehouses = frappe.get_all(
        "Warehouse", filters={"company": company, "is_group": 0}, pluck="name"
    )
    return tuple(warehouses)


def get_open_purchase_orders_items(items, company):
    # return the total of remaining qty of open purchase orders for each item that not delivered yet
    # fields: qty
    items_list = [item["item_code"] for item in items]
    items_list = tuple(items_list)
    if len(items_list) == 0:
        return items
    if len(items_list) == 1:
        items_list = f"""('{items_list[0]}')"""
    quantities = frappe.db.sql(
        f"""SELECT item_code, SUM(qty - received_qty) AS qty
            FROM `tabPurchase Order Item`
            INNER JOIN `tabPurchase Order` ON `tabPurchase Order Item`.parent = `tabPurchase Order`.name
            WHERE `tabPurchase Order`.docstatus = 1 
            AND `tabPurchase Order`.status != 'Closed' 
            AND `tabPurchase Order`.company = '{company}' 
            AND item_code IN {items_list}
            AND qty > received_qty
            GROUP BY item_code""",
        as_dict=True,
    )
    for item in items:
        for quantity in quantities:
            if item["item_code"] == quantity["item_code"]:
                item["open_purchase_qty"] = quantity["qty"]

    return items


def get_items_sales(company, from_date, to_date, item_group=None, items=None):
    # return the items from the actual sales invoices
    # fields: item_code, item_name, item_group, qty as sales_total, and calc sales_average qty

    conditions = f"""
        SI.docstatus = 1
        AND S.company = '{company}'
        AND S.posting_date BETWEEN '{from_date}' AND '{to_date}'
        """
    if item_group:
        groups = get_child_item_groups(item_group)
        groups = tuple(groups)
        if len(groups) == 1:
            groups = f"""('{groups[0]}')"""
        conditions += f""" AND SI.item_group IN {groups}"""

    if items and len(items) > 0:
        items_list = [item["item_code"] for item in items]
        items_list = tuple(items_list)
        if len(items_list) == 0:
            return items
        if len(items_list) == 1:
            items_list = f"""('{items_list[0]}')"""
        conditions += f""" AND SI.item_code IN {items_list}"""

    items_data = frappe.db.sql(
        f"""SELECT item_code, item_name, item_group, SUM(qty) AS sales_total
        FROM `tabSales Invoice Item` SI
        INNER JOIN `tabSales Invoice` S ON SI.parent = S.name
        WHERE {conditions}
        GROUP BY item_code""",
        as_dict=True,
    )

    # calculate sales monthly average based on from_date and to_date
    converted_start_date = frappe.utils.getdate(from_date)
    converted_end_date = frappe.utils.getdate(to_date)
    for item in items_data:
        item["sales_average"] = round(
            item["sales_total"]
            / ((converted_end_date - converted_start_date).days / 30),
            2,
        )

    if items:
        # update only sales_average and sales_total and retrun the updated items
        for item in items:
            for item_data in items_data:
                if item["item_code"] == item_data["item_code"]:
                    item["sales_average"] = item_data["sales_average"]
                    item["sales_total"] = item_data["sales_total"]
        return items

    else:
        return items_data
