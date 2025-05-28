import frappe
import threading
import time
from frappe.tests.utils import FrappeTestCase
from impex.extends.sales_invoice.sales_invoice import rename_invoice

class TestSalesInvoice(FrappeTestCase):
	def setUp(self):
		# Ensure required master data exists
		self._create_test_company()
		self._create_test_customer()
		self._create_test_item()
		self._create_test_invoice()

	def _create_test_company(self):
		if not frappe.db.exists("Company", "_Test Company"):
			frappe.get_doc({
				"doctype": "Company",
				"company_name": "_Test Company",
				"abbr": "TC",
				"default_currency": "BWP",
				"country": "United States",
				"default_currency": "BWP"
			}).insert()

	def _create_test_customer(self):
		if not frappe.db.exists("Customer", "_Test Customer"):
			frappe.get_doc({
				"doctype": "Customer",
				"customer_name": "_Test Customer",
				"customer_group": "All Customer Groups",
				"customer_type": "Company",
				"territory": "All Territories"
			}).insert()

	def _create_test_item(self):
		if not frappe.db.exists("Item", "_Test Item"):
			frappe.get_doc({
				"doctype": "Item",
				"item_code": "_Test Item",
				"item_name": "_Test Item",
				"item_group": "All Item Groups",
				"is_stock_item": 1,
				"stock_uom": "Nos"
			}).insert()

	def _create_test_invoice(self):
		self.invoice = frappe.get_doc({
			"doctype": "Sales Invoice",
			"naming_series": "TEST-INV-",
			"is_pos": 1,
			"company": "_Test Company",
			"posting_date": "2024-01-01",
			"customer": "_Test Customer",
			"items": [{
				"item_code": "_Test Item",
				"qty": 1,
				"rate": 100
			}]
		}).insert()

	def test_rename_with_deadlock(self):
		def concurrent_rename():
			frappe.db.begin()
			try:
				# Lock the naming series table
				frappe.db.sql("SELECT nextval('TEST-INV-') FOR UPDATE")
				time.sleep(2)
				frappe.db.commit()
			except:
				frappe.db.rollback()

		# Start concurrent transaction
		thread = threading.Thread(target=concurrent_rename)
		thread.start()
		
		# Small delay to ensure the thread starts
		time.sleep(0.5)
		
		# Try to rename - should trigger retry mechanism
		rename_invoice(self.invoice)
		
		# Wait for thread to complete
		thread.join()
		
		# Verify the rename worked
		self.assertNotEqual(self.invoice.name, "TEST-INV-")

	# def tearDown(self):
	# 	if frappe.db.exists("Sales Invoice", self.invoice.name):
	# 		frappe.delete_doc("Sales Invoice", self.invoice.name)