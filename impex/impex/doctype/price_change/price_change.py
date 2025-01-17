import frappe
from frappe.utils import flt
from frappe.model.document import Document


class PriceChange(Document):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._price_list_data = {}  # Cache for price list data
        self._existing_prices = {}  # Cache for existing prices

    def validate(self):
        self.load_price_list_data()
        self.calc_price_change()

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

        # First pass - calculate base prices
        base_prices = {}
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
                base_prices[rule.price_list] = rule.new_rate

        # Second pass - calculate dependent prices
        for rule in self.rule_prices:
            if rule.base_price_list:
                base_rate = base_prices.get(rule.base_price_list)
                if not base_rate:
                    frappe.throw(
                        f"Base Price rate not found for Price List {rule.base_price_list}"
                    )
                rule.new_rate = (
                    base_rate * (1 + (rule.margin / 100)) if rule.margin else base_rate
                )

    def update_item_price_from_price_change(self):
        """Bulk update item prices"""
        supplier_doc = frappe.get_cached_doc("Supplier", self.supplier)
        prices_to_update = []
        prices_to_create = []
        supplier_rules_modified = False

        for rule in self.rule_prices:
            if flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                # Check if price exists
                existing_price = frappe.db.exists(
                    "Item Price",
                    {
                        "item_code": rule.item_code,
                        "price_list": rule.price_list,
                    },
                )

                price_data = {
                    "item_code": rule.item_code,
                    "price_list": rule.price_list,
                    "price_list_rate": rule.new_rate,
                    "valid_from": self.posting_date,
                    "valid_upto": None,
                }

                if existing_price:
                    prices_to_update.append({"name": existing_price, **price_data})
                else:
                    prices_to_create.append(price_data)

            # Update supplier rules if needed
            if rule.update_sp:
                if self.update_supplier_rule(supplier_doc, rule):
                    supplier_rules_modified = True

        # Bulk update/create prices
        if prices_to_update:
            for price in prices_to_update:
                doc = frappe.get_cached_doc("Item Price", price.pop("name"))
                doc.update(price)
                doc.save(ignore_permissions=True)

        if prices_to_create:
            for price in prices_to_create:
                doc = frappe.get_doc({"doctype": "Item Price", **price})
                doc.insert(ignore_permissions=True)

        if supplier_rules_modified:
            supplier_doc.save(ignore_permissions=True)

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
        """Bulk delete created item prices"""
        item_prices = [r.item_price for r in self.rule_prices if r.item_price]
        if item_prices:
            frappe.db.delete("Item Price", {"name": ["in", item_prices]})


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

        # Check if any prices actually changed
        changed_prices = []
        for rule in price_change_doc.rule_prices:
            if flt(rule.new_rate, 2) != flt(rule.last_rate, 2):
                item_row = next(
                    (
                        item
                        for item in price_change_doc.items
                        if item.item_code == rule.item_code
                    ),
                    None,
                )
                # update if price list is buying
                if "Buying" in rule.price_list:
                    changed_prices.append(rule)
                # update if no last rate or rate change is greater than 2
                elif item_row and (
                    not new_item.last_rate or abs(item_row.rate_change) > 2
                ):
                    changed_prices.append(rule)

        if changed_prices:
            price_change_doc.rule_prices = changed_prices
            price_change_doc.save(ignore_permissions=True)
            url = frappe.utils.get_url_to_form("Price Change", price_change_doc.name)
            frappe.msgprint(
                f"Price Change Created <a href='{url}'>{price_change_doc.name}</a>"
            )
        else:
            frappe.msgprint("No Price Change Created, No Changes Found")
