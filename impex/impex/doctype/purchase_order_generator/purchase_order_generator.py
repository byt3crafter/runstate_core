# Copyright (c) 2024, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from erpnext.setup.doctype.item_group.item_group import get_child_item_groups
from frappe.utils import getdate
from frappe.utils import now_datetime


class PurchaseOrderGenerator(Document):
    def validate(self):
        pass

    def on_submit(self):
        self.validate_mandatory_fields()
        purchase_orders = self.create_purchase_orders()
        create_so = frappe.db.get_single_value("Impex Settings", "create_sales_order")
        if create_so and len(purchase_orders) > 0 and self.inter_company_purchase:
            create_sales_order(purchase_orders)

    def validate_mandatory_fields(self):
        if not self.items:
            frappe.throw(
                frappe._(
                    "You can not submit the Purchase Order Generator without items"
                )
            )
        for item in self.items:
            if not item.purchase_qty:
                frappe.throw(
                    frappe._(
                        f"Purchase qty is missing for item {item.item_code} {item.item_name} in row {item.idx}"
                    )
                )
            if not item.purchase_rate:
                frappe.throw(
                    frappe._(
                        f"Purchase rate is missing for item {item.item_code} {item.item_name} in row {item.idx}"
                    )
                )
            if not item.purchase_supplier:
                frappe.throw(
                    frappe._(
                        f"Purchase supplier is missing for item {item.item_code} {item.item_name} in row {item.idx}"
                    )
                )

    def create_purchase_orders(self):
        purchase_orders = []
        # group items by supplier and create a purchase order for each supplier
        today_date = getdate()
        items = {}
        for item in self.items:
            if item.purchase_supplier not in items:
                items[item.purchase_supplier] = [[]]
            # add items to the supplier list of items 50 items per purchase order as multiple items list
            if len(items[item.purchase_supplier][-1]) < 50:
                items[item.purchase_supplier][-1].append(item)
            else:
                items[item.purchase_supplier].append([item])
        
        # Get the default warehouse for the company and price list
        warehouse = frappe.db.get_value("Impex Company Settings", {"company": self.company}, "default_warehouse")
        if not warehouse or warehouse == "":
            frappe.throw(f"Please set the default warehouse for {self.company} in Impex Settings")
        if self.inter_company_purchase == 1:
            price_list = frappe.db.get_single_value("Impex Settings", "main_company_price_list")

        for supplier in items:
            for items_list in items[supplier]:
                purchase_order = frappe.new_doc("Purchase Order")
                purchase_order.supplier = supplier
                supplier_price_list = frappe.get_cached_value(
                    "Supplier", supplier, "default_price_list"
                )
                if self.inter_company_purchase == 1:
                    purchase_order.buying_price_list = price_list
                elif supplier_price_list:
                    purchase_order.buying_price_list = supplier_price_list
                purchase_order.company = self.company
                purchase_order.posting_date = today_date
                purchase_order.set("items", [])
                purchase_order.currency = items[supplier][0][0].purchase_currency
                conversion_rate = frappe.get_cached_value(
                    "Supplier", supplier, "exchange_rate"
                )
                if conversion_rate:
                    purchase_order.conversion_rate = conversion_rate

                for item in items_list:
                    purchase_order.append(
                        "items",
                        {
                            "item_code": item.item_code,
                            "item_name": item.item_name,
                            "item_group": item.item_group,
                            "qty": item.purchase_qty,
                            "rate": item.purchase_rate,
                            "schedule_date": (
                                item.purchase_date
                                if getdate(item.purchase_date) > today_date
                                else today_date
                            ),
                            "warehouse": warehouse
                        },
                    )
                    
                if self.company == frappe.db.get_single_value("Impex Settings", "main_company"):
                    tax_template = frappe.db.get_single_value("Impex Settings", "tax_template")
                else:
                    tax_template = frappe.db.get_value("Impex Company Settings", {"company": self.company}, "tax_template")
                    
                if tax_template:
                    purchase_order.taxes_and_charges = tax_template
                    taxes = frappe.get_all(
                        "Purchase Taxes and Charges",
                        filters={"parent": tax_template},
                        fields=["*"],
                        order_by="idx",
                    )
                    for tax in taxes:
                        purchase_order.append(
                            "taxes",
                            {
                                "charge_type": tax.charge_type,
                                "account_head": tax.account_head,
                                "description": tax.description,
                                "rate": tax.rate,
                                "tax_amount": tax.tax_amount,
                                "cost_center": tax.cost_center,
                                "included_in_print_rate": tax.included_in_print_rate,
                                "included_in_paid_amount": tax.included_in_paid_amount,
                            },
                        )
                
                if self.orders_in_draft:
                    purchase_order.save(ignore_permissions=True)
                else:
                    purchase_order.submit()
                purchase_order.reload()

                # set the purchase order name and item row in each item in the Purchase Order Generator Items table
                for item in items_list:
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
                link = frappe.utils.get_url_to_form(
                    "Purchase Order", purchase_order.name
                )
                frappe.msgprint(
                    f"""Purchase Order <a href="{link}">{purchase_order.name}</a>  is created for supplier {supplier}"""
                )
                purchase_orders.append(purchase_order.name)
        return purchase_orders

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

        # # set last purchase rate, qty, supplier, date for each item
        # items = get_last_purchase_transactions_record(items, self.company)
        # # set cheapest purchase rate, qty, supplier, date for each item
        # items = get_cheapest_purchase_transactions_record(
        #     items,
        #     self.company,
        #     self.from_date,
        #     self.to_date,
        # )

        # set the latest purchase transaction for each item from each supplier
        items = get_latest_purchase_transactions_record_for_each_supplier(
            items, self.company, self.from_date, self.to_date
        )

        # set existing stock qty for each item
        items = get_existing_stock_qty(items, self.company)

        # set open purchase orders qty for each item
        items = get_open_purchase_orders_items(items, self.company)

        # update the items table
        # If it's an inter-company transaction, replace the supplier with a supplier
        # representing the main company
        main_company_supplier = None
        if self.inter_company_purchase:
            main_company = frappe.db.get_single_value("Impex Settings", "main_company")
            
            if not main_company or main_company == "":
                frappe.throw("Please set the main company in Impex Settings to enable inter-company purchase functions")
                
            main_company_supplier = frappe.db.get_value("Supplier", {"represents_company": main_company}, "name")
        
            if main_company_supplier is None or main_company_supplier == "":
                frappe.throw(f"Please create a supplier for {main_company} to enable inter-company purchase functions")

            main_company_warehouse = frappe.db.get_single_value("Impex Settings", "main_company_warehouse")
            if not main_company_warehouse or main_company_warehouse == "":
                frappe.throw("Pleae set the default warehouse of the main company in Impex Settings")
        
        self.items = []
        for item in items:
            item = frappe._dict(item)
            # set required purchase qty for each item
            self.set_required_purchase_qty(item)
            # replace purchase supplier with preffered supplier if they have been set
            self.get_preffered_supplier(item)
            if item.purchase_qty > 0:
                if self.inter_company_purchase:
                    item.purchase_supplier = main_company_supplier
                    self.append("items", item)
                elif self.supplier:
                    if item.cheapest_purchase_supplier == self.supplier:
                        self.append("items", item)
                else:
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
        
        if self.inter_company_purchase == 1:
            price_list = frappe.db.get_single_value("Impex Settings", "main_company_price_list")
            if price_list and price_list != "":
                item.purchase_rate = frappe.db.get_value("Item Price", 
                                        {"price_list": price_list, "item_code": item.item_code}, "price_list_rate")
        else:
            item.purchase_rate = item.cheapest_purchase_rate or item.last_purchase_rate
            
        item.purchase_supplier = (
            item.cheapest_purchase_supplier or item.last_purchase_supplier
        )
        item.purchase_date = frappe.utils.today()
        item.purchase_currency = (
            item.cheapest_purchase_currency or item.last_purchase_currency
        )
        
    def get_preffered_supplier(self, item):
        # Check if there is a preffered supplier. If there is, then replace the purchase information with the suppliers
        supplier_exists = frappe.db.exists("Item Supplier", {"parent": item.item_code, "custom_preffered_supplier": 1})
        if supplier_exists:
            supplier = frappe.db.get_value("Item Supplier", supplier_exists, "supplier")
            item.purchase_supplier = supplier
            
            # Get the cheapest purchase rate for the supplier
            cheapest_purchase_rate = frappe.db.sql(
                f"""SELECT PI.rate, P.currency
                    FROM `tabPurchase Invoice Item` PI
                    INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                    WHERE PI.item_code = %(item_code)s AND P.company = %(company)s AND P.custom_special_order = 0 AND P.docstatus = 1 
                    	and P.is_return = 0 and P.posting_date BETWEEN %(from_date)s AND %(to_date)s AND P.supplier = %(supplier)s
                    ORDER BY PI.base_rate ASC
                    LIMIT 1""",
                {"item_code": item["item_code"], "company": self.company, "from_date": self.from_date, "to_date": self.to_date, "supplier": supplier},
                as_dict=True,
            )
            if len(cheapest_purchase_rate) > 0:
                item.purchase_rate = cheapest_purchase_rate[0].rate
                item.purchase_currency = cheapest_purchase_rate[0].currency
            else:
                item.purchase_rate = 0
                item.purchase_currency = ""
    
    @frappe.whitelist()
    def get_supplier_rate(self, item_code, supplier):
        cheapest_purchase_rate = frappe.db.sql(
                f"""SELECT PI.rate, P.currency
                    FROM `tabPurchase Invoice Item` PI
                    INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                    WHERE PI.item_code = %(item_code)s AND P.company = %(company)s AND P.custom_special_order = 0 AND P.docstatus = 1 
                    	and P.is_return = 0 and P.posting_date BETWEEN %(from_date)s AND %(to_date)s AND P.supplier = %(supplier)s
                    ORDER BY PI.base_rate ASC
                    LIMIT 1""",
                {"item_code": item_code, "company": self.company, "from_date": self.from_date, "to_date": self.to_date, "supplier": supplier},
                as_dict=True,
            )
        if len(cheapest_purchase_rate) > 0:
            purchase_rate = cheapest_purchase_rate[0].rate
            purchase_currency = cheapest_purchase_rate[0].currency    
        else:
            purchase_rate = 0
            purchase_currency = ""
        return {"purchase_rate": purchase_rate, "purchase_currency": purchase_currency}

def get_items_from_sales_orders(
    company, from_date, to_date, item_group=None, items=None
):
    # return the items from the unfulfilled sales orders
    # fields: item_code, item_name, item_group, qty, base_net_amount
    conditions = f"""
        SO.docstatus = 1 
        AND SO.status IN ('To Deliver and Bill', 'To Deliver') 
        AND SO.company = '{company}'
        AND SO.custom_special_order = 0
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
        # update only sales_orders_qty and base_net_amount and return the updated items
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
                WHERE PI.item_code = '{item["item_code"]}' AND P.company = '{company}' AND P.custom_special_order = 0 AND P.docstatus = 1 and P.is_return = 0
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


def get_cheapest_purchase_transactions_record(items, company, from_date, to_date):
    # return the cheapest purchase transaction for each item between from_date and to_date
    # fields: date , qty, rate, amount, supplier

    for item in items:
        cheapest_purchase_transaction = frappe.db.sql(
            f"""SELECT P.posting_date AS date, PI.qty, PI.rate, PI.amount, P.supplier, P.currency
                FROM `tabPurchase Invoice Item` PI
                INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                WHERE PI.item_code = '{item["item_code"]}' AND P.company = '{company}' AND P.custom_special_order = 0 AND P.docstatus = 1 and P.is_return = 0 and P.posting_date BETWEEN '{from_date}' AND '{to_date}'
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


def get_latest_purchase_transactions_record_for_each_supplier(
    items, company, from_date, to_date
):
    """
    Return the latest purchase transaction for each item from each supplier between from_date and to_date

    :param items: list of items
    :param company: company name
    :param from_date: start date
    :param to_date: end date
    """

    items_dict = {}
    for item in items:
        # get all suppliers for the item between from_date and to_date
        # only one last transaction record for each supplier
        item_suppliers = frappe.db.sql(
            f"""SELECT DISTINCT P.supplier AS supplier, P.posting_date AS date, PI.qty, PI.rate, PI.amount, P.currency
                FROM `tabPurchase Invoice Item` PI
                INNER JOIN `tabPurchase Invoice` P ON PI.parent = P.name
                WHERE PI.item_code = '{item["item_code"]}' AND P.company = '{company}' AND P.custom_special_order = 0 AND P.docstatus = 1 
                	and P.is_return = 0 and P.posting_date BETWEEN '{from_date}' AND '{to_date}'
                ORDER BY P.posting_date ASC""",
            as_dict=True,
        )

        if item.item_code not in items_dict:
            items_dict[item.item_code] = {}
        for supplier in item_suppliers:
            items_dict[item.item_code][supplier.supplier] = supplier

    # set the cheapest purchase transaction and the latest purchase transaction for each item from supplier
    for item in items:
        if item.item_code in items_dict:
            cheapest_supplier = None
            cheapest_rate = None
            cheapest_currency = None
            cheapest_date = None
            cheapest_qty = None
            latest_supplier = None
            latest_rate = None
            latest_currency = None
            latest_date = None
            latest_qty = None
            for supplier in items_dict[item.item_code]:
                if (
                    not cheapest_rate
                    or items_dict[item.item_code][supplier].rate < cheapest_rate
                ):
                    cheapest_supplier = supplier
                    cheapest_rate = items_dict[item.item_code][supplier].rate
                    cheapest_currency = items_dict[item.item_code][supplier].currency
                    cheapest_date = items_dict[item.item_code][supplier].date
                    cheapest_qty = items_dict[item.item_code][supplier].qty
                if (
                    not latest_date
                    or items_dict[item.item_code][supplier].date > latest_date
                ):
                    latest_supplier = supplier
                    latest_rate = items_dict[item.item_code][supplier].rate
                    latest_currency = items_dict[item.item_code][supplier].currency
                    latest_date = items_dict[item.item_code][supplier].date
                    latest_qty = items_dict[item.item_code][supplier].qty

            item["cheapest_purchase_rate"] = cheapest_rate
            item["cheapest_purchase_supplier"] = cheapest_supplier
            item["cheapest_purchase_qty"] = cheapest_qty
            item["cheapest_purchase_date"] = cheapest_date
            item["cheapest_purchase_currency"] = cheapest_currency

            item["last_purchase_rate"] = latest_rate
            item["last_purchase_supplier"] = latest_supplier
            item["last_purchase_qty"] = latest_qty
            item["last_purchase_date"] = latest_date
            item["last_purchase_currency"] = latest_currency

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
            GROUP BY item_code""",
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
            WHERE (`tabPurchase Order`.docstatus = 1 OR (`tabPurchase Order`.docstatus = 0 AND `tabPurchase Order`.dont_regenerate_in_draft = 1))
            AND `tabPurchase Order`.status != 'Closed' 
            AND `tabPurchase Order`.company = '{company}' 
            AND item_code IN {items_list}
            AND qty > received_qty
            AND `tabPurchase Order`.custom_special_order = 0
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
        AND S.custom_special_order = 0
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

def create_sales_order(purchase_orders):
    for purchase_order in purchase_orders:
        po = frappe.get_doc("Purchase Order", purchase_order)
        customer = frappe.db.get_value("Impex Company Settings", {"company": po.company}, "company_customer")
        company = frappe.db.get_single_value("Impex Settings", "main_company")
        warehouse = frappe.db.get_single_value("Impex Settings", "main_company_warehouse")
        price_list = frappe.db.get_single_value("Impex Settings", "main_company_price_list")
        so = frappe.new_doc("Sales Order")
        so.update({
            "company": company,
            "customer": customer,
            "transaction_date": now_datetime(),
            "set_warehouse": warehouse,
            "custom_branch_purchase_order": po.name
        })
        
        if price_list and price_list != "":
            so.update({"selling_price_list": price_list})
        
        for item in po.items:
            so.append("items", {
                "item_code": item.item_code,
                "delivery_date": item.schedule_date,
                "qty": item.qty,
                "uom": item.uom,
                "rate": item.rate,
                "custom_branch_purchase_order": po.name,
                "custom_branch_purchase_order_item": item.name,
                "warehouse": warehouse
            })
            
        sales_tax_template = frappe.db.get_single_value("Impex Settings", "sales_tax_template")
                    
        if sales_tax_template:
            so.taxes_and_charges = sales_tax_template
            taxes = frappe.get_all(
                        "Sales Taxes and Charges",
                        filters={"parent": sales_tax_template},
                        fields=["*"],
                        order_by="idx",
                    )
            for tax in taxes:
                so.append(
                    "taxes",
                    {
                        "charge_type": tax.charge_type,
                        "account_head": tax.account_head,
                        "description": tax.description,
                        "rate": tax.rate,
                        "tax_amount": tax.tax_amount,
                        "cost_center": tax.cost_center,
                        "included_in_print_rate": tax.included_in_print_rate,
                        "included_in_paid_amount": tax.included_in_paid_amount,
                    },
                )
        so.submit()
        
@frappe.whitelist()
def get_po_in_draft(company):
    return frappe.db.get_value("Impex Company Settings", {"company": company}, "po_in_draft")

@frappe.whitelist()
def get_item_suppliers(doctype, txt, searchfield, start, page_len, filters):
    item_code = filters.get('item_code')
    return frappe.db.sql("""
            SELECT
                supplier.name 
            FROM
                `tabItem Supplier` AS item
            LEFT JOIN
                `tabSupplier` AS supplier ON item.supplier = supplier.name
            WHERE
                item.parent = %(item_code)s AND supplier.name LIKE %(supplier)s
            """, {"item_code": item_code, "supplier": '%' + txt + '%'})

@frappe.whitelist()
def get_main_company():
    main_company = frappe.db.get_single_value("Impex Settings", "main_company")
    return main_company