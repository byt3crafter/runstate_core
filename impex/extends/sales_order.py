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


def create_pick_list(source_name, target_doc=None):
    from erpnext.stock.doctype.packed_item.packed_item import is_product_bundle

    def update_item_quantity(source, target, source_parent) -> None:
        picked_qty = flt(source.picked_qty) / (flt(source.conversion_factor) or 1)
        qty_to_be_picked = flt(source.qty) - max(picked_qty, flt(source.delivered_qty))

        target.qty = qty_to_be_picked
        target.stock_qty = qty_to_be_picked * flt(source.conversion_factor)

    def update_packed_item_qty(source, target, source_parent) -> None:
        qty = flt(source.qty)
        for item in source_parent.items:
            if source.parent_detail_docname == item.name:
                picked_qty = flt(item.picked_qty) / (flt(item.conversion_factor) or 1)
                pending_percent = (
                    item.qty - max(picked_qty, item.delivered_qty)
                ) / item.qty
                target.qty = target.stock_qty = qty * pending_percent
                return

    def should_pick_order_item(item, source_doc) -> bool:
        return (
            abs(item.delivered_qty) < abs(item.qty)
            and item.delivered_by_supplier != 1
            and not is_product_bundle(item.item_code)
            and is_item_in_company_stock(
                item.item_code, item.qty - item.delivered_qty, source_doc.company
            )
        )

    doc = get_mapped_doc(
        "Sales Order",
        source_name,
        {
            "Sales Order": {
                "doctype": "Pick List",
                "validation": {"docstatus": ["=", 1]},
            },
            "Sales Order Item": {
                "doctype": "Pick List Item",
                "field_map": {"parent": "sales_order", "name": "sales_order_item"},
                "postprocess": update_item_quantity,
                "condition": should_pick_order_item,
            },
            "Packed Item": {
                "doctype": "Pick List Item",
                "field_map": {
                    "parent": "sales_order",
                    "name": "sales_order_item",
                    "parent_detail_docname": "product_bundle_item",
                },
                "field_no_map": ["picked_qty"],
                "postprocess": update_packed_item_qty,
            },
        },
        target_doc,
    )

    doc.purpose = "Delivery"

    doc.set_item_locations()

    return doc


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

    for sales_order in sales_orders:
        try:
            doc = create_pick_list(sales_order.name)
            if doc.get("locations") and len(doc.locations) > 0:
                doc.save(ignore_permissions=True)
                doc.submit()
                frappe.db.commit()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to generate pick list for Sales Order {sales_order.name}.",
            )
            frappe.db.rollback()


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
