# Copyright (c) 2024, Yousef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt
from frappe.model.document import Document


class PriceChange(Document):
    def validate(self):
        self.calc_price_change()

    def before_submit(self):
        self.update_item_price_from_price_change()

    def before_cancel(self):
        self.delete_items_prices()

    def calc_price_change(self):
        for rule in self.rule_prices:
            rule.last_rate = 0
            # get last rate based on price list and item code and valid_from date
            existing_rate = frappe.get_all(
                "Item Price",
                filters={
                    "item_code": rule.item_code,
                    "price_list": rule.price_list,
                },
                fields=["name", "price_list_rate"],
                order_by="valid_from desc",
                limit=1,
            )
            if existing_rate:
                rule.last_rate = existing_rate[0].price_list_rate
            # calculate new rate if no base price list
            if not rule.base_price_list:
                # get item row from items child table in the self
                item_row = None
                for item in self.items:
                    if item.item_code == rule.item_code:
                        item_row = item
                        break
                if item_row:
                    rule.new_rate = (
                        item_row.base_rate * (1 + (rule.margin / 100))
                        if rule.margin
                        else item_row.base_rate
                    )
                else:
                    frappe.throw(f"Item {rule.item_code} not found in items table")
        # calc rates for price lists with base price list and update item price if rate changed
        for rule in self.rule_prices:
            if rule.base_price_list:
                base_price_list = None
                for rule1 in self.rule_prices:
                    if rule1.price_list == rule.base_price_list:
                        base_price_list = rule1
                        break
                if base_price_list:
                    if not base_price_list.new_rate:
                        frappe.throw(
                            f"Base Price rate {base_price_list.new_rate} not found for Price List {base_price_list.price_list}"
                        )
                    rule.new_rate = (
                        base_price_list.new_rate * (1 + (rule.margin / 100))
                        if rule.margin
                        else base_price_list.new_rate
                    )
                else:
                    frappe.throw(
                        f"Base Price List {rule.base_price_list} not found for Price List {rule.price_list}"
                    )

    def update_item_price_from_price_change(self):
        supplier_doc = frappe.get_cached_doc("Supplier", self.supplier)
        for rule in self.rule_prices:
            rule.last_rate = 0
            # get last rate based on price list and item code and valid_from date
            existing_rate = frappe.get_all(
                "Item Price",
                filters={
                    "item_code": rule.item_code,
                    "price_list": rule.price_list,
                },
                fields=["name", "price_list_rate"],
                order_by="valid_from desc",
                limit=1,
            )
            if existing_rate:
                rule.last_rate = existing_rate[0].price_list_rate
            # calculate new rate if no base price list
            if not rule.base_price_list:
                # get item row from items child table in the self
                item_row = None
                for item in self.items:
                    if item.item_code == rule.item_code:
                        item_row = item
                        break
                if item_row:
                    rule.new_rate = (
                        item_row.base_rate * (1 + (rule.margin / 100))
                        if rule.margin
                        else item_row.base_rate
                    )
                else:
                    frappe.throw(f"Item {rule.item_code} not found in items table")
        # calc rates for price lists with base price list and update item price if rate changed
        for rule in self.rule_prices:
            if rule.base_price_list:
                base_price_list = None
                for rule1 in self.rule_prices:
                    if rule1.price_list == rule.base_price_list:
                        base_price_list = rule1
                        break
                if base_price_list:
                    if not base_price_list.new_rate:
                        frappe.throw(
                            f"Base Price rate {base_price_list.new_rate} not found for Price List {base_price_list.price_list}"
                        )
                    rule.new_rate = (
                        base_price_list.new_rate * (1 + (rule.margin / 100))
                        if rule.margin
                        else base_price_list.new_rate
                    )
                else:
                    frappe.throw(
                        f"Base Price List {rule.base_price_list} not found for Price List {rule.price_list}"
                    )
            # update item price if rate changed
            if rule.new_rate != rule.last_rate:
                item_price = frappe.db.get_value(
                    "Item Price",
                    {
                        "item_code": rule.item_code,
                        "price_list": rule.price_list,
                        "valid_from": self.posting_date,
                    },
                    "name",
                )
                if item_price:
                    frappe.db.set_value(
                        "Item Price",
                        item_price,
                        "price_list_rate",
                        rule.new_rate,
                    )
                # rule.item_price = item_price
                else:
                    item_price = frappe.get_doc(
                        {
                            "doctype": "Item Price",
                            "item_code": rule.item_code,
                            "price_list": rule.price_list,
                            "price_list_rate": rule.new_rate,
                            "valid_from": self.posting_date,
                        }
                    ).insert(ignore_permissions=True)
                    # set item_price in rule
                    rule.item_price = item_price.name
            # update supplier in supplier doctype in rule_prices child table
            if rule.update_sp:
                # check if the rule is exist in supplier doctype
                supplier_rule = None
                for rule1 in supplier_doc.rule_prices:
                    if (
                        rule1.price_list == rule.price_list
                        and rule1.item_code == rule.item_code
                    ):
                        supplier_rule = rule1
                        break
                if supplier_rule:
                    supplier_rule.margin = rule.margin
                    supplier_rule.base_price_list = rule.base_price_list
                    supplier_rule.base_price_list = rule.base_price_list
                else:
                    supplier_doc.append(
                        "rule_prices",
                        {
                            "price_list": rule.price_list,
                            "margin": rule.margin,
                            "base_price_list": rule.base_price_list,
                            "item_code": rule.item_code,
                        },
                    )
        supplier_doc.save(ignore_permissions=True)

    def delete_items_prices(self):
        for rule in self.rule_prices:
            if rule.item_price:
                frappe.delete_doc("Item Price", rule.item_price)


@frappe.whitelist()
def create_price_change_from_purchase_invoice(
    doc=None, doctype="Purchase Invoice", doc_name=None
):

    if not doc and doctype and doc_name:
        doc = frappe.get_cached_doc(doctype, doc_name)

    if not doc:
        frappe.throw("Document not found")

    if not doc.get("is_return"):
        price_change_doc = frappe.new_doc("Price Change")
        if doc.doctype == "Purchase Invoice":
            price_change_doc.purchase_invoice = doc.name
        elif doc.doctype == "Purchase Order":
            price_change_doc.purchase_order = doc.name
        price_change_doc.posting_date = (
            doc.get("posting_date")
            or doc.get("transaction_date")
            or frappe.utils.nowdate()
        )
        price_change_doc.supplier = doc.supplier
        price_change_doc.items = []
        price_change_doc.currency = doc.currency
        supplier_doc = frappe.get_cached_doc(
            "Supplier", {"supplier_name": doc.supplier}
        )

        for item in doc.items:
            new_item = price_change_doc.append("items", item.as_dict())
            new_item.name = None
            new_item.ref_row_id = item.name

            # get latest purchase rate from purchase invoice item
            last_rates = frappe.db.sql(
                """
                SELECT
                    base_rate
                FROM
                    `tabPurchase Order Item`
                WHERE
                    item_code = %s
                    AND docstatus = 1
                    AND parent != %s
                ORDER BY
                    modified DESC
                LIMIT 1
                """,
                (item.item_code, doc.name),
            )
            if last_rates:
                latest_rate = last_rates[0][0]
                new_item.last_rate = latest_rate
                # calculate rate change percentage positive or negative
                if latest_rate and flt(latest_rate, 2) != flt(new_item.base_rate, 2):
                    new_item.rate_change = flt(
                        ((new_item.base_rate - latest_rate) / new_item.base_rate) * 100,
                        2,
                    )

                else:
                    new_item.rate_change = 0

            # get rules price from item group
            item_group_doc = frappe.get_cached_doc("Item Group", item.item_group)
            for group_rule in item_group_doc.rule_prices:
                price_change_doc.append(
                    "rule_prices",
                    {
                        "item_code": item.item_code,
                        "item_name": item.item_name,
                        "price_list": group_rule.price_list,
                        "margin": group_rule.margin,
                        "base_price_list": group_rule.base_price_list,
                        "source": "Item Group",
                    },
                )

            # get rules price from item and override existing rules
            item_doc = frappe.get_cached_doc("Item", item.item_code)
            for item_rule in item_doc.rule_prices:
                exists = False
                for rule in price_change_doc.rule_prices:
                    if (
                        rule.price_list == item_rule.price_list
                        and rule.item_code == item.item_code
                    ):
                        rule.margin = item_rule.margin
                        rule.base_price_list = item_rule.base_price_list
                        rule.source = "Item"
                        exists = True
                        break
                if not exists:
                    price_change_doc.append(
                        "rule_prices",
                        {
                            "item_code": item.item_code,
                            "item_name": item.item_name,
                            "price_list": item_rule.price_list,
                            "margin": item_rule.margin,
                            "base_price_list": item_rule.base_price_list,
                            "source": "Item",
                        },
                    )

            # get rules price from supplier and override existing rules
            for supplier_item in supplier_doc.rule_prices:
                exists = False
                for rule in price_change_doc.rule_prices:
                    if (
                        supplier_item.price_list == rule.price_list
                        and supplier_item.item_code == rule.item_code
                    ):
                        rule.margin = supplier_item.margin
                        rule.base_price_list = supplier_item.base_price_list
                        rule.source = "Supplier"
                        exists = True
                        break
                if not exists and supplier_item.item_code == item.item_code:
                    price_change_doc.append(
                        "rule_prices",
                        {
                            "item_code": item.item_code,
                            "item_name": item.item_name,
                            "price_list": supplier_item.price_list,
                            "margin": supplier_item.margin,
                            "base_price_list": supplier_item.base_price_list,
                            "source": "Supplier",
                        },
                    )

        if price_change_doc.items and len(price_change_doc.items) > 0:
            # check if the price change is changed
            price_change_doc_items_dict = {}
            for item in price_change_doc.items:
                price_change_doc_items_dict[item.item_code] = item
            there_is_change = False
            price_change_doc.calc_price_change()
            changed_prices = []

            for rule in price_change_doc.rule_prices:
                if flt(rule.new_rate) != flt(rule.last_rate):
                    there_is_change = True
                    item_row = price_change_doc_items_dict.get(rule.item_code)
                    # Apply only for buying price list or selling price list if item rate change is more than 2%
                    # check if the price list is selling or buying
                    if "Buying" in rule.price_list:
                        changed_prices.append(rule)
                    else:
                        # check for item Rate Change is more than 2%
                        if item_row and abs(item_row.rate_change) > 2:
                            changed_prices.append(rule)

            if there_is_change and changed_prices:
                price_change_doc.rule_prices = changed_prices
                price_change_doc.save(ignore_permissions=True)
                url = frappe.utils.get_url_to_form(
                    "Price Change", price_change_doc.name
                )
                frappe.msgprint(
                    f"Price Change Created <a href='{url}'>{price_change_doc.name}</a>"
                )
            else:
                frappe.msgprint("No Price Change Created, No Changes Found")
