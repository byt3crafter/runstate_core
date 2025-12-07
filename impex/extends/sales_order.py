import frappe
from impex.extends.mapper import get_mapped_doc
from frappe.utils import flt
from erpnext.stock.get_item_details import get_price_list_rate_for
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from erpnext.controllers.selling_controller import SellingController, set_default_income_account_for_item
from erpnext.controllers.stock_controller import StockController
from erpnext.manufacturing.doctype.blanket_order.blanket_order import (
	validate_against_blanket_order,
)
from erpnext.accounts.doctype.sales_invoice.sales_invoice import (
	validate_inter_company_party,
)
import json

class CustomStockController(StockController):
    def validate(self):
        super(CustomStockController, self).validate()

class CustomSellingController(CustomStockController, SellingController):
    def validate(self):
        CustomStockController.validate(self)
        self.validate_items()
        if not (self.get("is_debit_note") or self.get("is_return")):
            self.validate_max_discount()
        if not frappe.db.exists("Impex Company Settings", {"company": self.company, "disable_selling_prive_validation": 1}):
            self.validate_selling_price()
        self.set_qty_as_per_stock_uom()
        self.set_po_nos(for_validate=True)
        self.set_gross_profit()
        set_default_income_account_for_item(self)
        self.set_customer_address()
        self.validate_for_duplicate_items()
        self.validate_target_warehouse()
        self.validate_auto_repeat_subscription_dates()

class CustomSalesOrder(CustomSellingController, SalesOrder):
    def validate(self):
        CustomSellingController.validate(self)
        self.validate_delivery_date()
        self.validate_proj_cust()
        self.validate_po()
        self.validate_uom_is_integer("stock_uom", "stock_qty")
        self.validate_uom_is_integer("uom", "qty")
        self.validate_for_items()
        self.validate_warehouse()
        self.validate_drop_ship()
        self.validate_serial_no_based_delivery()
        validate_against_blanket_order(self)
        validate_inter_company_party(
            self.doctype, self.customer, self.company, self.inter_company_order_reference
        )

        if self.coupon_code:
            from erpnext.accounts.doctype.pricing_rule.utils import validate_coupon_code

            validate_coupon_code(self.coupon_code)

        from erpnext.stock.doctype.packed_item.packed_item import make_packing_list

        make_packing_list(self)

        self.validate_with_previous_doc()
        self.set_status()

        if not self.billing_status:
            self.billing_status = "Not Billed"
        if not self.delivery_status:
            self.delivery_status = "Not Delivered"

        self.reset_default_field_value("set_warehouse", "items", "warehouse")
        prompt_same_items(self)

# def validate(doc, method=None):
#     prompt_same_items(doc)


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

def verify_pick_list_exists(pick_list_name):
    """
    Thoroughly verify if a pick list exists in the database with detailed checking.
    """
    print(f"\n=== Verifying Pick List {pick_list_name} ===")
    
    try:
        # Method 1: Direct exists check
        exists_check = frappe.db.exists("Pick List", pick_list_name)
        print(f"Method 1 - Direct exists check: {exists_check}")

        # Method 2: SQL query check
        sql_check = frappe.db.sql("""
            SELECT name, docstatus, creation, modified 
            FROM `tabPick List` 
            WHERE name = %s
        """, pick_list_name, as_dict=1)
        print(f"Method 2 - SQL query check: {bool(sql_check)}")
        if sql_check:
            print(f"Details: {sql_check[0]}")

        # Method 3: Get doc check
        try:
            doc_check = frappe.get_doc("Pick List", pick_list_name)
            print(f"Method 3 - Get doc check: {bool(doc_check)}")
            print(f"Document status: {doc_check.docstatus}")
            print(f"Creation time: {doc_check.creation}")
            print(f"Number of items: {len(doc_check.locations)}")
        except Exception as e:
            print(f"Method 3 - Get doc failed: {str(e)}")

        return {
            'exists_check': bool(exists_check),
            'sql_check': bool(sql_check),
            'doc_check': bool(doc_check if 'doc_check' in locals() else False)
        }

    except Exception as e:
        print(f"Error during verification: {str(e)}")
        return {
            'exists_check': False,
            'sql_check': False,
            'doc_check': False
        }

def generate_pick_lists():
    """
    Generate pick lists for all pending sales orders, skipping already picked items without failing.
    Log all created Pick Lists and Sales Orders in a single log entry.
    """
    print("\n=== Starting Pick List Generation ===")
    
    log_rows = []  # Collect rows for the log table

    try:
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={
                "docstatus": 1,
                "status": ["not in", ["Closed", "Completed", "Cancelled"]],
            },
            fields=["name"]
        )
        print(f"Found {len(sales_orders)} active sales orders")

        customers_orders_dict = {}
        for so in sales_orders:
            order_doc = frappe.get_cached_doc("Sales Order", so.name)
            if order_doc.customer not in customers_orders_dict:
                customers_orders_dict[order_doc.customer] = []
            customers_orders_dict[order_doc.customer].append(order_doc)

        for customer, orders in customers_orders_dict.items():
            print(f"\nProcessing customer: {customer}")
            
            # Collect eligible items
            items = []
            for order in orders:
                for item in order.items:
                    remaining_qty = abs(item.qty) - abs(item.delivered_qty)
                    if (remaining_qty > 0 
                        and item.delivered_by_supplier != 1 
                        and is_item_in_company_stock(
                            item.item_code,
                            remaining_qty,
                            order.company
                        )):
                        items.append(item)

            if not items:
                print(f"No eligible items found for customer: {customer}")
                continue

            # Process items in batches of 25
            for i in range(0, len(items), 25):
                items_batch = items[i:i + 25]
                try:
                    print(f"\nCreating pick list for {len(items_batch)} items")
                    
                    # First, verify which items are already picked
                    unpicked_items = []
                    for item in items_batch:
                        existing_pick = frappe.db.exists({
                            'doctype': 'Pick List Item',
                            'parenttype': 'Pick List',
                            'docstatus': ['<', 2],
                            'item_code': item.item_code,
                            'sales_order': item.parent,
                            'sales_order_item': item.name
                        })
                        
                        if existing_pick:
                            print(f"Skipping already picked item: {item.item_code}")
                        else:
                            unpicked_items.append(item)

                    if not unpicked_items:
                        print("No unpicked items in this batch")
                        continue

                    print(f"Creating pick list with {len(unpicked_items)} unpicked items")
                    pick_list = frappe.new_doc("Pick List")
                    pick_list.customer = customer
                    pick_list.purpose = "Delivery"
                    pick_list.company = orders[0].company

                    for item in unpicked_items:
                        remaining_qty = abs(item.qty) - abs(item.delivered_qty)
                        print(f"Adding to pick list: {item.item_code}")
                        pick_list.append(
                            "locations",
                            {
                                "item_code": item.item_code,
                                "item_name": item.item_name,
                                "description": item.description,
                                "uom": item.uom,
                                "stock_uom": item.stock_uom,
                                "conversion_factor": item.conversion_factor,
                                "qty": remaining_qty,
                                "stock_qty": remaining_qty * item.conversion_factor,
                                "sales_order": item.parent,
                                "sales_order_item": item.name,
                            }
                        )

                    if pick_list.locations:
                        print("\nSetting item locations...")
                        pick_list.set_item_locations()
                        
                        try:
                            print("\nAttempting to save pick list...")
                            pick_list.flags.ignore_validate = True # Try to bypass validationist.flags.ignore
                            pick_list.flags.ignore_mandatory = True # Skip mandatory field validationmandatoryignore_
                            pick_list.save(ignore_permissions=True)
                            print(f"Successfully saved pick list: {pick_list.name}")
                            
                            # Verify save was successful
                            # if frappe.db.exists("Pick List", pick_list.name):
                            #     print(f"Verified pick list exists in database: {pick_list.name}")
                            # else:
                            #     print(f"WARNING: Pick list may not have been saved properly")
                            log_rows.append({
                                "customer": customer,
                                "sales_order": orders[0].name,
                                "pick_list": pick_list.name,
                                "status": "Success"
                            })
                                
                        except Exception as save_error:
                            print(f"Error during save: {str(save_error)}")
                            # Try alternative save method if normal save fails
                            try:
                                print("Attempting alternative save method...")
                                pick_list.insert(ignore_permissions=True)
                                frappe.db.commit()
                                print(f"Successfully saved pick list using alternative method: {pick_list.name}")
                                
                                log_rows.append({
                                    "customer": customer,
                                    "sales_order": orders[0].name,
                                    "pick_list": pick_list.name,
                                    "status": "Success"
                                })
                            except Exception as alt_error:
                                log_rows.append({
                                    "customer": customer,
                                    "sales_order": orders[0].name,
                                    "status": "Failed",
                                    "error_message": str(e)
                                })
                                print(f"Alternative save method also failed: {str(alt_error)}")

                except Exception as e:
                    print(f"\nERROR creating pick list batch:")
                    print(f"Error message: {str(e)}")
                    frappe.log_error(
                        frappe.get_traceback(),
                        f"Pick list generation failed for customer {customer}"
                    )

    except Exception as outer_e:
        print(f"\nERROR in pick list generation:")
        print(f"Error type: {type(outer_e).__name__}")
        print(f"Error message: {str(outer_e)}")
        frappe.log_error(
            frappe.get_traceback(),
            "Pick list generation failed"
        )
    finally:
        # Generate the log details and save them in a log entry
        log_details = generate_log_details(log_rows)
        frappe.get_doc({
            "doctype": "Pick List Generation Log",
            "log_details": log_details
        }).insert(ignore_permissions=True)
        print("\n=== Pick List Generation Completed ===")
        frappe.msgprint("Pick list generation process completed")

@frappe.whitelist()
def background_update_sales_orders_prices():
    frappe.errprint("Enqueuing background job to update sales orders prices")
    frappe.enqueue("impex.extends.sales_order.update_sales_orders_prices", queue="long")
    frappe.errprint("Background job enqueued successfully")
    return "Prices are being updated in the background."


@frappe.whitelist()
def background_update_sales_orders_prices():
    frappe.enqueue("impex.extends.sales_order.update_sales_orders_prices", queue="long")
    return "Prices are being updated in the background."

def update_sales_orders_prices():
    """Update prices for all uncompleted sales orders"""
    print("Starting batch update of sales order prices")
    
    all_log_rows = []  # Collect all changes across all orders
    
    sales_orders = frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": ["!=", 2],
            "status": ["not in", ["Closed", "Completed", "Cancelled"]],
        },
        fields=["name"],
    )
    
    print(f"Found {len(sales_orders)} sales orders to process")
    
    for sales_order in sales_orders:
        try:
            print(f"\nProcessing Sales Order: {sales_order.name}")
            so = frappe.get_cached_doc("Sales Order", sales_order.name)
            print(f"SO Date: {so.transaction_date}, Customer: {so.customer}, Price List: {so.selling_price_list}")
            
            # Collect changes from each order
            log_rows = update_sales_order_prices(so)
            if log_rows:
                all_log_rows.extend(log_rows)
                
        except Exception as e:
            print(f"Error processing SO {sales_order.name}: {str(e)}")
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed to update prices for Sales Order {sales_order.name}.",
            )
            frappe.db.rollback()
    
    # Create single log entry with all changes
    if all_log_rows:
        log_details = generate_price_update_log(all_log_rows)
        frappe.get_doc({
            "doctype": "Sales Order Price Update Log",
            "log_details": log_details
        }).insert(ignore_permissions=True)
    
    print("\n=== Price Update Completed ===")

def get_latest_price_list_rate(item_code, price_list):
    """Get the latest price based on valid_from date"""
    latest_price = frappe.get_all(
        "Item Price",
        filters={
            "item_code": item_code,
            "price_list": price_list,
        },
        fields=["price_list_rate", "valid_from"],
        order_by="valid_from desc",
        limit=1
    )
    
    if latest_price:
        print(f"Latest price found for {item_code}:")
        print(f"Rate: {latest_price[0].price_list_rate}")
        print(f"Valid From: {latest_price[0].valid_from}")
        return latest_price[0]
    return None

def update_sales_order_prices(so):
    """Update prices for a single sales order"""
    print(f"\nChecking prices for SO {so.name}")
    
    log_rows = []
    there_is_a_change = False
    items_changed = []
    
    for item in so.items:
        print(f"\nProcessing item: {item.item_code}")
        print(f"Current rate: {item.rate}")
        print(f"Delivered qty: {item.delivered_qty} / Total qty: {item.qty}")
        
        # Skip fully delivered items
        if flt(item.delivered_qty) >= flt(item.qty):
            print(f"Skipping {item.item_code} - Fully delivered")
            log_rows.append({
                "sales_order": so.name,
                "item_code": item.item_code,
                "status": "Skipped",
                "error_message": "Fully delivered"
            })
            continue
        
        # Get latest price with valid_from date
        latest_price_data = get_latest_price_list_rate(item.item_code, so.selling_price_list)
        
        if latest_price_data:
            latest_price = latest_price_data.price_list_rate
            valid_from = latest_price_data.valid_from
            
            print(f"Price comparison for {item.item_code}:")
            print(f"Current rate: {flt(item.rate, 2)}")
            print(f"Latest price: {flt(latest_price, 2)} (Valid from: {valid_from})")
            
            if flt(latest_price, 2) != flt(item.rate, 2):
                print(f"Price update needed for {item.item_code}")
                print(f"Old rate: {item.rate}, New rate: {latest_price}")
                
                old_amount = item.amount
                new_amount = flt(item.qty * latest_price, 2)
                
                # Force update the database directly
                print(f"Forcing DB update for item {item.name}")
                
                # Update the database directly
                frappe.db.set_value('Sales Order Item', item.name, {
                    'rate': latest_price,
                    'base_rate': latest_price,
                    'amount': new_amount,
                    'base_amount': new_amount,
                    'margin_rate_or_amount': 0,
                    'discount_percentage': 0,
                    'discount_amount': 0,
                    'price_list_rate': latest_price
                }, update_modified=True)
                
                # Update the object to match DB
                item.rate = latest_price
                item.amount = new_amount
                item.price_list_rate = latest_price
                
                print(f"Updated amounts - Old: {old_amount}, New: {new_amount}")
                print(f"Verified new rate in DB: {frappe.db.get_value('Sales Order Item', item.name, 'rate')}")
                
                there_is_a_change = True
                items_changed.append({
                    "item_code": item.item_code,
                    "old_rate": flt(old_amount/item.qty, 2),
                    "new_rate": flt(latest_price, 2),
                    "valid_from": valid_from
                })
                
                # Add to log rows only if price was actually changed
                log_rows.append({
                    "sales_order": so.name,
                    "item_code": item.item_code,
                    "old_rate": flt(old_amount/item.qty, 2),
                    "new_rate": flt(latest_price, 2),
                    "valid_from": valid_from,
                    "status": "Updated"
                })
            else:
                print(f"No price change needed for {item.item_code}")
                log_rows.append({
                    "sales_order": so.name,
                    "item_code": item.item_code,
                    "old_rate": item.rate,
                    "new_rate": item.rate,
                    "status": "No Change"
                })
        else:
            print(f"No price found in price list for {item.item_code}")
            log_rows.append({
                "sales_order": so.name,
                "item_code": item.item_code,
                "status": "Error",
                "error_message": "No price found in price list"
            })
    
    if there_is_a_change:
        print(f"\nChanges detected for SO {so.name}")
        print("Items changed:")
        for item in items_changed:
            print(f"- {item['item_code']}: {item['old_rate']} -> {item['new_rate']} (Valid from: {item['valid_from']})")
        
        old_total = so.total
        so.calculate_taxes_and_totals()
        print(f"Totals - Old: {old_total}, New: {so.total}")
        
        # Update the SO total in DB
        frappe.db.set_value('Sales Order', so.name, {
            'total': so.total,
            'grand_total': so.grand_total,
            'rounded_total': so.rounded_total,
            'base_total': so.base_total,
            'base_grand_total': so.base_grand_total,
            'base_rounded_total': so.base_rounded_total
        }, update_modified=True)
        
        try:
            # Create detailed comment
            comment_items = [f"{item['item_code']} ({item['old_rate']} -> {item['new_rate']})" 
                           for item in items_changed]
            
            comment_text = f"""Prices have been automatically updated based on the latest price list:
Items updated: {', '.join(comment_items)}"""
            
            so.add_comment("Comment", comment_text)
            
            frappe.db.commit()
            
        except Exception as e:
            print(f"Error updating SO {so.name}: {str(e)}")
            print(f"Items that were changed: {json.dumps(items_changed, indent=2)}")
            raise
    
    return log_rows  # Return the log rows instead of creating a log

def generate_log_details(rows):
    """
    Generate the HTML log details for the Pick List Generation Log, including the header and rows.
    :param rows: A list of dictionaries, where each dictionary represents a row with keys:
                 - customer
                 - sales_order
                 - pick_list
                 - status
                 - error_message
    :return: A string containing the complete HTML table with links to the Sales Order, Pick List, and Customer.
    """
    log_details = "<h3>Pick List Generation Log</h3>"
    log_details += "<table style='border-collapse: collapse; width: 100%;'>"
    log_details += "<tr style='background-color: #f2f2f2;'>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Customer</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Sales Order</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Pick List</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Status</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Error Message</th>"
    log_details += "</tr>"

    for row in rows:
        customer = row.get('customer', '')
        sales_order = row.get('sales_order', '')
        pick_list = row.get('pick_list', 'N/A')

        # Generate links for Customer, Sales Order, and Pick List
        customer_link = (
            f"<a href='{frappe.utils.get_url_to_form('Customer', customer)}'>{customer}</a>"
            if customer else ''
        )
        sales_order_link = (
            f"<a href='{frappe.utils.get_url_to_form('Sales Order', sales_order)}'>{sales_order}</a>"
            if sales_order else ''
        )
        pick_list_link = (
            f"<a href='{frappe.utils.get_url_to_form('Pick List', pick_list)}'>{pick_list}</a>"
            if pick_list != 'N/A' else 'N/A'
        )

        log_details += "<tr>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{customer_link}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{sales_order_link}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{pick_list_link}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{row.get('status', 'Success')}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{row.get('error_message', '')}</td>"
        log_details += "</tr>"

    log_details += "</table>"
    return log_details

def generate_price_update_log(rows):
    """
    Generate HTML log for Sales Order price updates, showing only actual changes.
    :param rows: List of dictionaries containing update details
    :return: HTML string containing formatted log table of changed prices
    """
    # Filter rows to only include actual price changes
    changed_rows = [row for row in rows if row.get('status') == 'Updated']
    
    if not changed_rows:
        return "<h3>Sales Order Price Update Log</h3><p>No prices were changed during this update.</p>"
    
    log_details = "<h3>Sales Order Price Update Log</h3>"
    log_details += "<p>The following prices were updated:</p>"
    log_details += "<table style='border-collapse: collapse; width: 100%;'>"
    log_details += "<tr style='background-color: #f2f2f2;'>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Sales Order</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Item Code</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Old Rate</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>New Rate</th>"
    log_details += "<th style='padding: 8px; border: 1px solid #ddd;'>Valid From</th>"
    log_details += "</tr>"

    for row in changed_rows:
        sales_order = row.get('sales_order', '')
        item_code = row.get('item_code', '')
        
        # Generate link for Sales Order
        sales_order_link = (
            f"<a href='{frappe.utils.get_url_to_form('Sales Order', sales_order)}'>{sales_order}</a>"
            if sales_order else ''
        )
        
        # Generate link for Item
        item_link = (
            f"<a href='{frappe.utils.get_url_to_form('Item', item_code)}'>{item_code}</a>"
            if item_code else ''
        )

        log_details += "<tr>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{sales_order_link}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{item_link}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{row.get('old_rate', 'N/A')}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{row.get('new_rate', 'N/A')}</td>"
        log_details += f"<td style='padding: 8px; border: 1px solid #ddd;'>{row.get('valid_from', 'N/A')}</td>"
        log_details += "</tr>"

    log_details += "</table>"
    
    # Add summary at the bottom
    log_details += f"<p>Total items updated: {len(changed_rows)}</p>"
    return log_details
