import frappe
from frappe.utils import flt
from frappe.model.document import Document

Default_Price_Change_Threshold = 2


class PriceChange(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._price_list_data = {}  # Cache for price list data
        self._existing_prices = {}  # Cache for existing prices

    def validate(self):
        self.load_price_list_data()
        self.calc_price_change()
        self.load_changed_prices()

    def before_submit(self):
        self.update_item_price_from_price_change()

    def before_cancel(self):
        self.delete_items_prices()

    def load_price_list_data(self):
        """Preload all required price list data"""
        # Get all unique price lists
        price_lists = {rule.price_list for rule in self.rule_prices}
        base_price_lists = {
            rule.base_price_list for rule in self.rule_prices if rule.base_price_list
        }
        all_price_lists = list(price_lists | base_price_lists)

        # Bulk fetch existing prices
        if all_price_lists:
            item_codes = {rule.item_code for rule in self.rule_prices}
            existing_prices = frappe.get_all(
                "Item Price",
                filters={
                    "item_code": ["in", list(item_codes)],
                    "price_list": ["in", all_price_lists],
                },
                fields=["name", "price_list_rate", "item_code", "price_list"],
                order_by="valid_from desc",
            )

            # Index prices for quick lookup
            for price in existing_prices:
                key = f"{price.item_code}:{price.price_list}"
                if key not in self._existing_prices:
                    self._existing_prices[key] = price.price_list_rate

    def get_last_rate(self, item_code, price_list):
        """Get last rate from cache"""
        key = f"{item_code}:{price_list}"
        return self._existing_prices.get(key, 0)

    def calc_price_change(self):
        """Calculate new rates for all rules"""
        # Ensure price data is loaded
        if not self._existing_prices:
            self.load_price_list_data()

        # Initialize base_prices dictionary to store calculated prices
        base_prices = {}
        # Track processed rules to avoid infinite loops
        processed_rules = set()
        # Track rules with dependencies for later processing
        rules_with_dependencies = []

        # First pass - calculate base prices (rules without dependencies)
        for rule in self.rule_prices:
            rule.last_rate = self.get_last_rate(rule.item_code, rule.price_list)

            if not rule.base_price_list:
                # Find matching item
                item_row = next(
                    (item for item in self.items if item.item_code == rule.item_code),
                    None,
                )
                if not item_row:
                    frappe.throw(f"Item {rule.item_code} not found in items table")

                base_rate = item_row.base_rate
                rule.new_rate = (
                    base_rate * (1 + (rule.margin / 100)) if rule.margin else base_rate
                )

                if rule.last_rate and flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                    rule.rate_change = flt(
                        ((rule.new_rate - rule.last_rate) / rule.new_rate) * 100,
                        2,
                    )
                else:
                    rule.rate_change = 0
                
                if not base_prices.get(rule.price_list):
                    base_prices[rule.price_list] = {}
                base_prices[rule.price_list][rule.item_code] = rule.new_rate
                processed_rules.add(f"{rule.price_list}:{rule.item_code}")
            else:
                # Add to rules with dependencies for later processing
                rules_with_dependencies.append(rule)

        # Process rules with dependencies until all are processed or no progress is made
        remaining_rules = rules_with_dependencies.copy()
        while remaining_rules:
            rules_processed_in_this_iteration = 0
            still_remaining = []

            for rule in remaining_rules:
                if f"{rule.base_price_list}:{rule.item_code}" in processed_rules:
                    # Base price list has been processed, we can calculate this rule
                    base_rate = base_prices.get(rule.base_price_list, {}).get(rule.item_code)
                    rule.new_rate = (
                        base_rate * (1 + (rule.margin / 100))
                        if rule.margin and rule.margin != 0
                        else base_rate
                    )
                    
                    if rule.last_rate and flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                        rule.rate_change = flt(
                            ((rule.new_rate - rule.last_rate) / rule.new_rate) * 100,
                            2,
                        )
                    else:
                        rule.rate_change = 0
                    
                    if not base_prices.get(rule.price_list):
                        base_prices[rule.price_list] = {}
                    base_prices[rule.price_list][rule.item_code] = rule.new_rate
                    processed_rules.add(f"{rule.price_list}:{rule.item_code}")
                    
                    rules_processed_in_this_iteration += 1
                else:
                    # Base price list not processed yet, keep for next iteration
                    still_remaining.append(rule)

            # If we didn't process any rules in this iteration, we have circular dependencies
            if rules_processed_in_this_iteration == 0 and still_remaining:
                # Find the first unprocessed rule to report in the error
                unprocessed_rule = still_remaining[0]
                frappe.throw(
                    f"""Could not resolve price list dependencies. Base Price List '{unprocessed_rule.base_price_list}' for 
                    	'{unprocessed_rule.price_list}' could not be calculated. Check for circular dependencies. For Item {unprocessed_rule.item_code}"""
                )

            remaining_rules = still_remaining
        
    def load_changed_prices(self):
        # price_change_threshold = Default_Price_Change_Threshold
        # try:
        #     price_change_threshold = frappe.db.get_single_value(
        #         "Price Change Settings", "price_change_threshold"
        #     )
        # except Exception:
        #     price_change_threshold = Default_Price_Change_Threshold
        self.changed_prices = []
        for rule in self.rule_prices:
            if not rule.last_rate or flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                # if "Buying" in rule.price_list or (not rule.last_rate
                #         or abs(rule.rate_change) > price_change_threshold
                #     ):
                self.append("changed_prices", {
                    "item_code": rule.item_code,
                    "price_list": rule.price_list,
                    "old_rate": rule.last_rate,
                    "new_rate": rule.new_rate
                })
        

    def update_item_price_from_price_change(self):
        """Bulk update item prices"""
        supplier_doc = frappe.get_cached_doc("Supplier", self.supplier)
        prices_to_update = []
        prices_to_create = []
        rules_to_update = []  # Track rules that need item_price update
        supplier_rules_modified = False

        for rule in self.rule_prices:
            if flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                # item_row = next(
                #     (
                #         item
                #         for item in self.items
                #         if item.item_code == rule.item_code
                #     ),
                #     None,
                # )
                
                # # update if price list is buying or if no last rate or rate change is greater than 2
                # price_change_threshold = Default_Price_Change_Threshold
                # try:
                #     price_change_threshold = frappe.db.get_single_value(
                #         "Price Change Settings", "price_change_threshold"
                #     )
                # except Exception:
                #     price_change_threshold = Default_Price_Change_Threshold
                    
                # if "Buying" in rule.price_list or (item_row and (
                #         not item_row.last_rate
                #         or abs(item_row.rate_change) > price_change_threshold
                #     )):
                if not rule.last_rate or flt(rule.new_rate, 2) != flt(rule.last_rate, 2):  
                    # Check if price exists
                    existing_price = frappe.db.get_value(
                        "Item Price",
                        {
                            "item_code": rule.item_code,
                            "price_list": rule.price_list,
                        },
                        "name",
                    )

                    price_data = {
                        "item_code": rule.item_code,
                        "price_list": rule.price_list,
                        "price_list_rate": rule.new_rate,
                        "valid_from": self.posting_date,
                        "valid_upto": None,
                        "doctype": "Item Price",
                    }

                    if existing_price:
                        prices_to_update.append(
                            {"name": existing_price, "rule": rule, **price_data}
                        )
                    else:
                        prices_to_create.append({"rule": rule, **price_data})

                # Update supplier rules if needed
                if rule.update_sp:
                    if self.update_supplier_rule(supplier_doc, rule):
                        supplier_rules_modified = True

        # Bulk update/create prices
        if prices_to_update:
            for price in prices_to_update:
                rule = price.pop("rule")
                doc = frappe.get_cached_doc("Item Price", price.pop("name"))
                doc.update(price)
                doc.save(ignore_permissions=True)
                # Track rule and item_price for update
                rules_to_update.append({"name": rule.name, "item_price": doc.name})
                # Update rule's item_price in memory
                rule.item_price = doc.name

        if prices_to_create:
            for price in prices_to_create:
                rule = price.pop("rule")
                doc = frappe.get_doc(price)  # price_data already includes doctype
                doc.insert(ignore_permissions=True)
                # Track rule and item_price for update
                rules_to_update.append({"name": rule.name, "item_price": doc.name})
                # Update rule's item_price in memory
                rule.item_price = doc.name

        if supplier_rules_modified:
            supplier_doc.save(ignore_permissions=True)

        # Update item_price values directly in the database
        if rules_to_update:
            # Bulk update all rules at once
            for rule_update in rules_to_update:
                frappe.db.set_value(
                    "Price Change Rule",
                    rule_update["name"],
                    "item_price",
                    rule_update["item_price"],
                    update_modified=False,
                )
            frappe.db.commit()

    def update_supplier_rule(self, supplier_doc, rule):
        """Update supplier pricing rules"""
        existing_rule = next(
            (
                r
                for r in supplier_doc.rule_prices
                if r.price_list == rule.price_list and r.item_code == rule.item_code
            ),
            None,
        )

        modified = False
        if existing_rule:
            if (
                existing_rule.margin != rule.margin
                or existing_rule.base_price_list != rule.base_price_list
            ):
                existing_rule.margin = rule.margin
                existing_rule.base_price_list = rule.base_price_list
                modified = True
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
            modified = True

        return modified

    def delete_items_prices(self):
        """Restore/delete item prices based on version history"""
        item_prices_to_delete = []
        item_prices_to_restore = []

        # Get all item prices that need to be handled
        all_item_prices = [r.item_price for r in self.rule_prices if r.item_price]
        if not all_item_prices:
            return

        # Get all versions for item prices created/updated by this document
        versions = frappe.get_all(
            "Version",
            filters={
                "ref_doctype": "Item Price",
                "docname": ["in", all_item_prices],
            },
            fields=["name", "docname", "data", "creation"],
            order_by="creation desc",  # Get newest versions first
        )

        # Group versions by item price
        versions_by_price = {}
        for version in versions:
            if version.docname not in versions_by_price:
                versions_by_price[version.docname] = []
            versions_by_price[version.docname].append(version)

        for item_price, item_versions in versions_by_price.items():
            # Get the first (newest) version
            first_version = item_versions[0]
            version_data = frappe.parse_json(first_version.data)

            # Check if this was a new item price or an update
            if version_data.get("added"):
                # If it was newly created, we should delete it
                item_prices_to_delete.append(first_version.docname)
            elif version_data.get("changed"):
                # If it was an update, we should restore the old values
                restore_data = {}
                for field, old_value, new_value in version_data["changed"]:
                    if field == "price_list_rate":
                        # Handle currency formatted values
                        try:
                            # Remove currency symbol and convert to float
                            old_value = float(
                                old_value.replace("₺", "")
                                .replace(".", "")
                                .replace(",", ".")
                                .strip()
                            )
                        except Exception:
                            continue
                    elif field in ["valid_from", "valid_upto"]:
                        # Convert date string to proper format if it's a date field
                        if old_value:
                            try:
                                # Parse the date string and convert to YYYY-MM-DD
                                parsed_date = frappe.utils.get_datetime(old_value)
                                old_value = parsed_date.strftime("%Y-%m-%d")
                            except Exception:
                                continue

                    restore_data[field] = old_value

                if restore_data:
                    item_prices_to_restore.append(
                        {"name": first_version.docname, "data": restore_data}
                    )

        # Add prices without versions to delete list (they must be new)
        prices_with_versions = set(versions_by_price.keys())
        prices_without_versions = set(all_item_prices) - prices_with_versions
        if prices_without_versions:
            item_prices_to_delete.extend(list(prices_without_versions))

        # Bulk restore old values
        for item_price in item_prices_to_restore:
            try:
                doc = frappe.get_doc("Item Price", item_price["name"])
                doc.update(item_price["data"])
                doc.save(ignore_permissions=True)
            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 100:
                    error_msg = error_msg[:97] + "..."
                frappe.log_error(
                    f"Failed to restore Item Price {item_price['name']}: {error_msg}"
                )

        # Bulk delete newly created prices
        if item_prices_to_delete:
            try:
                frappe.db.delete("Item Price", {"name": ["in", item_prices_to_delete]})
            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 100:
                    error_msg = error_msg[:97] + "..."
                frappe.log_error(f"Failed to delete Item Prices: {error_msg}")


@frappe.whitelist()
def create_price_change_from_purchase_invoice(
    doc=None, doctype="Purchase Invoice", doc_name=None
):
    """Create Price Change document from Purchase Invoice/Order"""
    if not doc and doctype and doc_name:
        doc = frappe.get_cached_doc(doctype, doc_name)

    if not doc:
        frappe.throw("Document not found")

    if doc.get("is_return"):
        return
    
	# If it's not the main company return
    main_company = frappe.db.get_single_value("Impex Settings", "main_company")
    if doc.company != main_company:
        return

    # Prepare data
    items_data = {}  # Cache for item data
    price_lists = set()  # Track unique price lists
    supplier_doc = frappe.get_cached_doc("Supplier", {"supplier_name": doc.supplier})

    # Create Price Change doc
    price_change_doc = frappe.new_doc("Price Change")
    price_change_doc.update(
        {
            f"{doc.doctype.lower().replace(' ', '_')}": doc.name,
            "posting_date": (
                doc.get("posting_date")
                or doc.get("transaction_date")
                or frappe.utils.nowdate()
            ),
            "supplier": doc.supplier,
            "currency": doc.currency,
        }
    )

    # Bulk fetch latest rates
    if doc.items:
        item_codes = [item.item_code for item in doc.items]
        last_rates = frappe.db.sql(
            """
            SELECT 
                item_code,
                base_rate
            FROM `tabPurchase Order Item`
            WHERE item_code IN %s
                AND docstatus = 1
                AND parent != %s
                AND creation = (
                    SELECT MAX(creation)
                    FROM `tabPurchase Order Item` t2
                    WHERE t2.item_code = `tabPurchase Order Item`.item_code
                    AND t2.docstatus = 1
                    AND t2.parent != %s
                )
        """,
            (tuple(item_codes), doc.name, doc.name),
            as_dict=1,
        )

        # Index rates by item_code
        last_rates_dict = {r.item_code: r.base_rate for r in last_rates}
    
    # update if price list is buying or if no last rate or rate change is greater than 2
    # price_change_threshold = Default_Price_Change_Threshold
    # try:
    #     price_change_threshold = frappe.db.get_single_value(
    #         "Price Change Settings", "price_change_threshold"
    #     )
    # except Exception:
    #     price_change_threshold = Default_Price_Change_Threshold
    
    # Process items
    for item in doc.items:
        # Add item to Price Change
        new_item = price_change_doc.append("items", item.as_dict())
        new_item.name = None
        new_item.ref_row_id = item.name

        # Set last rate and calculate change
        last_rate = last_rates_dict.get(item.item_code, 0)
        new_item.last_rate = last_rate
        if last_rate and flt(last_rate, 2) != flt(new_item.base_rate, 2):
            new_item.rate_change = flt(
                ((new_item.base_rate - last_rate) / new_item.base_rate) * 100,
                2,
            )
        else:
            new_item.rate_change = 0

        # Cache item data for rules
        if item.item_code not in items_data:
            items_data[item.item_code] = {
                "item_group": frappe.get_cached_doc("Item Group", item.item_group),
                "item": frappe.get_cached_doc("Item", item.item_code),
                "rules": {},
            }

        # Get rules from Item Group
        for group_rule in items_data[item.item_code]["item_group"].rule_prices:
            price_lists.add(group_rule.price_list)
            items_data[item.item_code]["rules"][group_rule.price_list] = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "price_list": group_rule.price_list,
                "margin": group_rule.margin,
                "base_price_list": group_rule.base_price_list,
                "source": "Item Group",
            }

        # Override with Item rules
        for item_rule in items_data[item.item_code]["item"].rule_prices:
            price_lists.add(item_rule.price_list)
            items_data[item.item_code]["rules"][item_rule.price_list] = {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "price_list": item_rule.price_list,
                "margin": item_rule.margin,
                "base_price_list": item_rule.base_price_list,
                "source": "Item",
            }

        # Override with Supplier rules
        for supplier_rule in supplier_doc.rule_prices:
            if supplier_rule.item_code == item.item_code:
                price_lists.add(supplier_rule.price_list)
                items_data[item.item_code]["rules"][supplier_rule.price_list] = {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "price_list": supplier_rule.price_list,
                    "margin": supplier_rule.margin,
                    "base_price_list": supplier_rule.base_price_list,
                    "source": "Supplier",
                }
        
    # Add all rules to price change doc
    for item_data in items_data.values():
        for rule in item_data["rules"].values():
            price_change_doc.append("rule_prices", rule)

    if price_change_doc.items:
        # Calculate prices to check for changes
        price_change_doc.calc_price_change()

        # price_change_threshold = Default_Price_Change_Threshold
        # try:
        #     price_change_threshold = frappe.db.get_single_value(
        #         "Price Change Settings", "price_change_threshold"
        #     )
        # except Exception:
        #     price_change_threshold = Default_Price_Change_Threshold

        # Check if any prices actually changed
        changed_prices = []
        for rule in price_change_doc.rule_prices:
            if not rule.last_rate or flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                # item_row = next(
                #     (
                #         item
                #         for item in price_change_doc.items
                #         if item.item_code == rule.item_code
                #     ),
                #     None,
                # )
                # # update if price list is buying
                # if "Buying" in rule.price_list:
                #     changed_prices.append(rule)
                # # update if no last rate or rate change is greater than 2
                # elif item_row and (
                #     not item_row.last_rate
                #     or abs(item_row.rate_change) > price_change_threshold
                # ):
                changed_prices.append(rule)

        if changed_prices:
            #price_change_doc.rule_prices = changed_prices
            price_change_doc.save(ignore_permissions=True)
            url = frappe.utils.get_url_to_form("Price Change", price_change_doc.name)
            frappe.msgprint(
                f"Price Change Created <a href='{url}'>{price_change_doc.name}</a>"
            )
        else:
            frappe.msgprint("No Price Change Created, No Changes Found")

@frappe.whitelist()
def recalculate_zero_rated_item_prices():
    """Create Price Change document for items with stock balances but zero rated prices
      for selling price lists grouped by their Purchase Order or Purchase Invoice."""
    
    # Get all items that have 0 item price but have stock balance > 0
    items = frappe.db.sql("""
        SELECT DISTINCT
            item.name AS item_code,
            item.item_name,
            item.item_group
        FROM 
            `tabItem` AS item
        LEFT JOIN 
            `tabItem Price` AS price ON item.name = price.item_code
        LEFT JOIN 
            `tabBin` AS bin ON item.name = bin.item_code
        WHERE 
            price.price_list_rate = 0
            AND bin.actual_qty > 0
            AND item.disabled = 0
            AND item.is_stock_item = 1
            AND price.price_list NOT LIKE '%Buying%'
    """, as_dict=1)

    # Group items by their last Purchase Order or Purchase Invoice
    grouped_items = {}

    for item in items:
        item_code = item["item_code"]

        # Fetch the last Purchase Order for the item
        last_purchase_order = frappe.db.sql("""
            SELECT
                po.name AS reference_name, po.transaction_date AS posting_date,
                po.company, po.currency, po.supplier, poi.base_rate, poi.rate,
                poi.name AS ref_row_id, poi.qty, poi.uom, poi.stock_qty,
                poi.amount, poi.base_amount
            FROM
                `tabPurchase Order` AS po
            INNER JOIN
                `tabPurchase Order Item` AS poi ON po.name = poi.parent
            WHERE
                poi.item_code = %(item_code)s
                AND po.docstatus = 1
            ORDER BY
                po.transaction_date DESC
            LIMIT 1
        """, {"item_code": item_code}, as_dict=1)

        # If no Purchase Order exists, fetch the last Purchase Invoice
        if not last_purchase_order:
            last_purchase_invoice = frappe.db.sql("""
                SELECT
                    pi.name AS reference_name, pi.posting_date, pi.company,
                    pi.currency, pi.supplier, pii.base_rate, pii.rate,
                    pii.name AS ref_row_id, pii.qty, pii.uom, pii.stock_qty,
                    pii.amount, pii.base_amount
                FROM
                    `tabPurchase Invoice` AS pi
                INNER JOIN
                    `tabPurchase Invoice Item` AS pii ON pi.name = pii.parent
                WHERE
                    pii.item_code = %(item_code)s
                    AND pi.docstatus = 1
                ORDER BY
                    pi.posting_date DESC
                LIMIT 1
            """, {"item_code": item_code}, as_dict=1)

            if last_purchase_invoice:
                reference = last_purchase_invoice[0]
                key = f"Invoice:{reference.reference_name}"
                doc_type = "Purchase Invoice"
            else:
                continue
        else:
            reference = last_purchase_order[0]
            key = f"Order:{reference.reference_name}"
            doc_type = "Purchase Order"

        # Check if it's the main company
        main_company = frappe.db.get_single_value("Impex Settings", "main_company")
        if reference.company != main_company:
            continue

        # Initialize group if not exists
        if key not in grouped_items:
            grouped_items[key] = {
                "doc_type": doc_type,
                "reference": reference,
                "items": [],
                "items_data": {},
                "price_lists": set()
            }

        # Add item to group
        grouped_items[key]["items"].append({
            "item_code": item_code,
            "item_name": item["item_name"],
            "item_group": item["item_group"],
            "base_rate": reference.base_rate,
            "rate": reference.rate,
            "ref_row_id": reference.ref_row_id,
            "qty": reference.qty, 
            "uom": reference.uom, 
            "stock_qty": reference.stock_qty,
            "amount": reference.amount, 
            "base_amount": reference.base_amount
        })

    # Create Price Change documents for each group
    for group_key, group_data in grouped_items.items():
        # Create Price Change doc
        price_change_doc = frappe.new_doc("Price Change")
        price_change_doc.update({
            f"{group_data['doc_type'].lower().replace(' ', '_')}": group_data["reference"].reference_name,
            "posting_date": group_data["reference"].posting_date,
            "supplier": group_data["reference"].supplier,
            "currency": group_data["reference"].currency,
        })

        # Get supplier document
        supplier_doc = frappe.get_cached_doc("Supplier", group_data["reference"].supplier)

        # Process items and rules
        for item in group_data["items"]:
            # Add item to Price Change
            new_item = price_change_doc.append("items", item)
            
            # Cache item data for rules
            if item["item_code"] not in group_data["items_data"]:
                group_data["items_data"][item["item_code"]] = {
                    "item_group": frappe.get_cached_doc("Item Group", item["item_group"]),
                    "item": frappe.get_cached_doc("Item", item["item_code"]),
                    "rules": {}
                }

            # Get rules from Item Group
            for group_rule in group_data["items_data"][item["item_code"]]["item_group"].rule_prices:
                group_data["price_lists"].add(group_rule.price_list)
                group_data["items_data"][item["item_code"]]["rules"][group_rule.price_list] = {
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "price_list": group_rule.price_list,
                    "margin": group_rule.margin,
                    "base_price_list": group_rule.base_price_list,
                    "source": "Item Group"
                }

            # Override with Item rules
            for item_rule in group_data["items_data"][item["item_code"]]["item"].rule_prices:
                group_data["price_lists"].add(item_rule.price_list)
                group_data["items_data"][item["item_code"]]["rules"][item_rule.price_list] = {
                    "item_code": item["item_code"],
                    "item_name": item["item_name"],
                    "price_list": item_rule.price_list,
                    "margin": item_rule.margin,
                    "base_price_list": item_rule.base_price_list,
                    "source": "Item"
                }

            # Override with Supplier rules
            for supplier_rule in supplier_doc.rule_prices:
                if supplier_rule.item_code == item["item_code"]:
                    group_data["price_lists"].add(supplier_rule.price_list)
                    group_data["items_data"][item["item_code"]]["rules"][supplier_rule.price_list] = {
                        "item_code": item["item_code"],
                        "item_name": item["item_name"],
                        "price_list": supplier_rule.price_list,
                        "margin": supplier_rule.margin,
                        "base_price_list": supplier_rule.base_price_list,
                        "source": "Supplier"
                    }

        # Add all rules to price change doc
        for item_data in group_data["items_data"].values():
            for rule in item_data["rules"].values():
                price_change_doc.append("rule_prices", rule)

        if price_change_doc.items:
            # Calculate prices
            price_change_doc.calc_price_change()

            # Check for price changes
            # price_change_threshold = frappe.db.get_single_value(
            #     "Price Change Settings", 
            #     "price_change_threshold"
            # ) or Default_Price_Change_Threshold

            changed_prices = []
            for rule in price_change_doc.rule_prices:
                if not rule.last_rate or flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                    # item_row = next(
                    #     (item for item in price_change_doc.items if item.item_code == rule.item_code),
                    #     None
                    # )
                    # if "Buying" in rule.price_list:
                    #     changed_prices.append(rule)
                    # elif item_row and (
                    #     not item_row.last_rate
                    #     or abs(item_row.rate_change) > price_change_threshold
                    # ):
                    changed_prices.append(rule)

            if changed_prices:
                price_change_doc.save(ignore_permissions=True)
                url = frappe.utils.get_url_to_form("Price Change", price_change_doc.name)
                frappe.msgprint(
                    f"Price Change Created for {group_key}: <a href='{url}'>{price_change_doc.name}</a>"
                )

def add_auto_price_rules(doctype, docname):
    rule_exists = frappe.db.exists("Impex Settings Automatic Rule", {"document": doctype})
    if rule_exists:
        all_rules = frappe.db.get_all("Impex Settings Automatic Rule", 
                        filters={"document": doctype},
                        fields=["price_list", "margin", "base_price_list", "name"])
        
        # Get parent document to properly manage idx values
        doc = frappe.get_doc(doctype, docname)
        existing_rules = len(doc.rule_prices) if hasattr(doc, 'rule_prices') else 0
        
        for rule in all_rules:
            exists = frappe.db.exists(
                "Rule Prices", 
                {"parent": docname, "parenttype": doctype, "price_list": rule.price_list}
            )
    
            if exists:
                # Update existing rule
                frappe.db.set_value(
                    "Rule Prices", 
                    exists, 
                    {
                        "margin": rule.margin,
                        "base_price_list": rule.base_price_list
                    }
                )
            else:
                # Create new rule
                new_rule = frappe.get_doc({
                    "doctype": "Rule Prices",
                    "parenttype": doctype,
                    "parent": docname,
                    "parentfield": "rule_prices",
                    "price_list": rule.price_list,
                    "margin": rule.margin,
                    "base_price_list": rule.base_price_list,
                    "idx": existing_rules + 1
                })
                new_rule.insert(ignore_permissions=True)

@frappe.whitelist()
def add_item_rule_price(item_code: str, price_list: str, margin: float, base_price_list: str | None = None, for_company: str | None = None):
    """
    Add or update a Rule Prices child row under the Item doctype.
    - Avoid duplicates per (price_list, for_company) if possible.
    - If an existing row matches, update its margin/base_price_list.
    """
    if not item_code or not price_list:
        frappe.throw("Item Code and Price List are required")

    doc = frappe.get_doc("Item", item_code)

    # Determine the company field name on child doctype if present
    # company_field = None
    # rule_meta = frappe.get_meta("Rule Prices")
    # if rule_meta.has_field("for_company"):
    #     company_field = "for_company"
    # elif rule_meta.has_field("company"):
    #     company_field = "company"
    
    # Try to find an existing rule row
    existing = None
    for row in doc.rule_prices:
        if row.price_list == price_list and row.company == for_company:
            existing = row
            break

    if existing:
        existing.margin = flt(margin)
        existing.base_price_list = base_price_list or ""
    else:
        payload = {
            "price_list": price_list,
            "margin": flt(margin),
            "base_price_list": base_price_list or "",
            "company": for_company
        }
        doc.append("rule_prices", payload)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "item_code": item_code,
        "price_list": price_list,
        "margin": flt(margin),
        "base_price_list": base_price_list or "",
        "for_company": for_company or "",
        "status": "success"
    }

@frappe.whitelist()
def get_item_rule_prices(item_code: str, for_company: str | None = None):
    """
    Return Rule Prices child rows for an Item filtered by company (if provided).
    Includes child row name for UI actions (edit/delete).
    """
    if not item_code:
        return []
    filters = {
        "parenttype": "Item",
        "parent": item_code,
    }
    if for_company:
        filters["company"] = for_company

    rows = frappe.get_all(
        "Rule Prices",
        filters=filters,
        fields=["name", "price_list", "margin", "base_price_list", "company"],
        order_by="idx asc"
    )
    return rows

@frappe.whitelist()
def delete_item_rule_prices(item_code: str, names):
    """
    Delete Rule Prices child rows by name for the given Item.
    Safely updates the child table via the parent document to keep idx consistent.
    """
    if isinstance(names, str):
        try:
            names = frappe.parse_json(names)
        except Exception:
            names = [names]
    names = names or []
    if not item_code or not names:
        return {"deleted": 0, "removed": []}

    doc = frappe.get_doc("Item", item_code)
    keep = []
    removed = []
    for row in doc.rule_prices:
        if row.name in names:
            removed.append(row.name)
        else:
            keep.append(row)

    if not removed:
        return {"deleted": 0, "removed": []}

    doc.set("rule_prices", keep)
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {"deleted": len(removed), "removed": removed}

