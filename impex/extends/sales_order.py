import frappe
from impex.extends.mapper import get_mapped_doc
from frappe.utils import flt
from erpnext.stock.get_item_details import get_price_list_rate_for


def validate(doc, method=None):
    prompt_same_items(doc)


def prompt_same_items(doc):
    """
    Inform the user if the item already ordered for the same customer and not fully delivered.
    """
    not_delivered_items = []
    for item in doc.items:
        if item.item_code:
            item_code = item.item_code
            customer = doc.customer
            so = frappe.db.sql(
                """
                SELECT
                    so.name, soi.qty, soi.delivered_qty, soi.item_code, soi.delivery_date
                FROM
                    `tabSales Order` so
                INNER JOIN
                    `tabSales Order Item` soi
                ON
                    so.name = soi.parent
                WHERE
                    so.docstatus = 1
                AND
                    so.status != 'Closed'
                AND
                    so.customer = %(customer)s
                AND
                    soi.item_code = %(item_code)s
                AND
                    soi.delivered_qty < soi.qty
                AND
                    so.name != %(name)s
                """,
                values={
                    "customer": customer,
                    "item_code": item_code,
                    "name": doc.name,
                },
                as_dict=True,
            )
            if so:
                not_delivered_items.extend(so)

    if not_delivered_items:
        # display table with not delivered items to the user
        msg = "<table style='border-collapse: collapse; width: 100%;'>"
        msg += "<tr style='background-color: #f2f2f2;'>"
        msg += "<th style='padding: 8px; border: 1px solid #ddd;'>Order</th>"
        msg += "<th style='padding: 8px; border: 1px solid #ddd;'>Item</th>"
        msg += "<th style='padding: 8px; border: 1px solid #ddd;'>Remaining</th>"
        msg += "</tr>"

        for item in not_delivered_items:
            order_url = frappe.utils.get_url_to_form(
                doctype="Sales Order", name=item.name
            )
            msg += "<tr>"
            msg += f"<td style='padding: 8px; border: 1px solid #ddd;'> <a href='{order_url}'>{item.name}</a></td>"
            msg += f"<td style='padding: 8px; border: 1px solid #ddd;'>{item.item_code}</td>"
            msg += f"<td style='padding: 8px; border: 1px solid #ddd;'>{item.qty - item.delivered_qty}</td>"
            msg += "</tr>"

        msg += "</table>"

        frappe.msgprint(
            msg,
            title="The following items are already ordered for this customer and not fully delivered.",
            indicator="red",
        )


def is_item_in_stock(item_code, warehouse, qty):
    """
    Check if the item is in stock in the given warehouse and the quantity is available.
    """
    item_info = frappe.db.sql(
        """
        SELECT
            bin.actual_qty
        FROM
            `tabBin` bin
        WHERE
            bin.item_code = %(item_code)s
            AND bin.actual_qty >= %(qty)s
        AND
            bin.warehouse = %(warehouse)s
        """,
        values={
            "item_code": item_code,
            "warehouse": warehouse,
        },
        as_dict=True,
    )

    if item_info:
        return item_info[0].actual_qty >= qty

    return False


def is_item_in_company_stock(item_code, qty, company):
    """
    Check if the item is in stock in the given company and the quantity is available.
    """
    item_info = frappe.db.sql(
        """
        SELECT
            bin.actual_qty
        FROM
            `tabBin` bin
        INNER JOIN
            `tabWarehouse` wh
        ON
            bin.warehouse = wh.name
        WHERE
            bin.item_code = %(item_code)s
            AND bin.actual_qty >= %(qty)s
        AND
            wh.company = %(company)s
        """,
        values={
            "item_code": item_code,
            "company": company,
            "qty": qty,
        },
        as_dict=True,
    )

    if item_info:
        return item_info[0].actual_qty >= qty

    return False


@frappe.whitelist()
def background_generate_pick_lists():
    frappe.enqueue("impex.extends.sales_order.generate_pick_lists")
    return "Pick lists are being generated in the background."


def generate_pick_lists():
    """
    Generate pick lists for all sales orders that have not been delivered yet or partially delivered.
    """
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": 1,
            "status": ["not in", ["Closed", "Completed", "Cancelled"]],
        },
        fields=["name"],
    )

    customers_orders_dict = {}

    for sales_order in sales_orders:
        order_doc = frappe.get_cached_doc("Sales Order", sales_order.name)
        if order_doc.customer not in customers_orders_dict:
            customers_orders_dict[order_doc.customer] = []
        customers_orders_dict[order_doc.customer].append(order_doc)

    for customer, orders in customers_orders_dict.items():
        ## group the items from the orders by customer and no more 25 items per pick list
        items = []
        for order in orders:
            for item in order.items:
                if (
                    abs(item.delivered_qty) < abs(item.qty)
                    and item.delivered_by_supplier != 1
                    and is_item_in_company_stock(
                        item.item_code, item.qty - item.delivered_qty, order.company
                    )
                ):
                    items.append(item)

        items_grouped = [items[i : i + 25] for i in range(0, len(items), 25)]

        for items_set in items_grouped:
            if items_set:
                try:
                    pick_list = frappe.new_doc("Pick List")
                    pick_list.customer = customer
                    pick_list.purpose = "Delivery"
                    pick_list.company = orders[0].company

                    for pick_list_item in items_set:
                        pick_list.append(
                            "locations",
                            {
                                "item_code": pick_list_item.item_code,
                                "item_name": pick_list_item.item_name,
                                "description": pick_list_item.description,
                                "uom": pick_list_item.uom,
                                "stock_uom": pick_list_item.stock_uom,
                                "conversion_factor": pick_list_item.conversion_factor,
                                "qty": pick_list_item.qty
                                - pick_list_item.delivered_qty,
                                "stock_qty": (
                                    pick_list_item.qty - pick_list_item.delivered_qty
                                )
                                * pick_list_item.conversion_factor,
                                "sales_order": pick_list_item.parent,
                                "sales_order_item": pick_list_item.name,
                            },
                        )

                    if len(pick_list.locations) > 0:
                        pick_list.set_item_locations()
                        pick_list.save(ignore_permissions=True)
                        # pick_list.submit()

                except Exception:
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"Failed to generate pick list for customer {customer}.",
                    )

    frappe.msgprint("Pick lists have been generated.")


def update_sales_orders_prices():
    # a routine to update the prices of all uncompleted sales orders based on the latest price list and currency exchange rate
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": ["!=", 2],
            "status": ["not in", ["Closed", "Completed", "Cancelled"]],
        },
        fields=["name"],
    )

    for sales_order in sales_orders:
        try:
            so = frappe.get_cached_doc("Sales Order", sales_order.name)
            update_sales_order_prices(so)
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to update prices for Sales Order {sales_order.name}.",
            )
            frappe.db.rollback()


def update_sales_order_prices(so):
    there_is_a_change = False
    items_changed = []
    for item in so.items:
        args = {
            "price_list": so.selling_price_list,
            "customer": so.customer,
            "uom": item.uom,
            "transaction_date": so.transaction_date,
            "qty": item.qty,
        }
        last_price_list_rate = get_price_list_rate_for(args, item.item_code)
        if last_price_list_rate and flt(last_price_list_rate, 2) != flt(item.rate, 2):
            there_is_a_change = True
            items_changed.append(item.item_code)
            item.rate = last_price_list_rate
            item.amount = item.qty * item.rate
            item.price_list_rate = last_price_list_rate
    if there_is_a_change:
        so.calculate_taxes_and_totals()
        if so.docstatus == 0:
            # if doc is not submitted, save it without checking permissions
            so.save(ignore_permissions=True)
        elif so.docstatus == 1:
            # if doc is submitted, update the doc
            so.flags.ignore_validate_update_after_submit = True
            so.save(ignore_permissions=True)

        # add a comment to the sales order
        so.add_comment(
            "Comment",
            "Prices have been automatically updated based on the latest price list, for items: {}".format(
                ", ".join(items_changed)
            ),
        )

        frappe.db.commit()
