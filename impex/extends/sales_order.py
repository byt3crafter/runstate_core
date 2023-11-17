import frappe


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
