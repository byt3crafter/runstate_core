# -*- coding: utf-8 -*-
# Copyright (c) 2021, riconova and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class SupplierStatement(Document):

	def validate(self):
		self.get_data()
	
	@frappe.whitelist()
	def get_data(self):
		clause_supplier = ""
		if not self.supplier :
			frappe.throw("Please choose the supplier first")

		if not self.posting_date :
			frappe.throw("Please choose the posting date first")

		self.invoice_list = []

		get_sup = frappe.get_doc("Supplier", self. supplier)

		# ambil data SINV -
		get_sinv = frappe.db.sql("""
			SELECT sinv.`name`, sinv.`is_return`, sinv.`posting_date`, sinv.`due_date`, sinv.`outstanding_amount`
				, DATEDIFF(sinv.`due_date`, CURDATE()), sinv.`currency`, sinv.grand_total
			FROM `tabPurchase Invoice` sinv
			LEFT JOIN `tabPurchase Invoice` pinv ON sinv.return_against = pinv.name AND pinv.outstanding_amount > 0
			WHERE sinv.`docstatus` = 1
			AND sinv.`supplier` = "{}"
			AND sinv.`posting_date` <= "{}"
			and (sinv.outstanding_amount > 0 or pinv.name is not null)
			ORDER BY sinv.`posting_date` ASC, sinv.`posting_time` ASC
		""".format(self.supplier,self.posting_date), as_dict = 1)

		# get_sinv = frappe.db.sql("""
		# 	SELECT sinv.`name`, sinv.`is_return`, sinv.`posting_date`, sinv.`due_date`, sinv.`outstanding_amount`, sinv.`po_no`, DATEDIFF(sinv.`due_date`, CURDATE()) 
		# 	FROM `tabPurchase Invoice` sinv
		# 	WHERE sinv.`docstatus` = 1
		# 	AND sinv.`outstanding_amount` > 0
		# 	AND sinv.`supplier` = "{}"
		# 	AND MONTH(sinv.`posting_date`) = MONTH("{}")
		# 	AND sinv.`posting_date` <= "{}"
		# 	ORDER BY sinv.`posting_date` ASC, sinv.`posting_time` ASC	
		# """.format(self.supplier, self.posting_date, self.posting_date))

		if get_sinv :
			total_balance = 0
			for i in get_sinv :

				child = self.append("invoice_list", {})
				child.date = i.posting_date
				child.doc_no = i.name
				
				if i.is_return == 0 :
					child.doc_type = "Purchase Invoice"
					child.invoice_amount = i.outstanding_amount
					child.debit_note = 0
				else :
					child.doc_type = "Debit Note"
					child.invoice_amount = 0
					# child.debit_note = i.outstanding_amount * -1
					child.debit_note = i.grand_total

				# total_balance += (child.invoice_amount - child.debit_note)				
				total_balance += child.invoice_amount + child.debit_note				
				child.balance = total_balance
				child.due_date = i.due_date

				child.supplier_currency = get_sup.default_currency

			self.supplier_currency = get_sup.default_currency
			
			out_amount = frappe.db.sql("""
				SELECT 
			 SUM(IF(sinv.posting_date between DATE_FORMAT("{posting_date}",'%Y-%m-01') and "{posting_date}", sinv.outstanding_amount,0)) `current`
			 -- find previous month total outstanding
			 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -1 MONTH)),'%Y-%m-01') 
		 								AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -1 MONTH)), sinv.outstanding_amount,0)) `thirty`
			 -- find 2 previous month total outstanding
			 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -2 MONTH)),'%Y-%m-01') 
			 							AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -2 MONTH)), sinv.outstanding_amount,0)) `sixty`
			 -- find 3 previous month total outstanding
			 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)),'%Y-%m-01') 
			 							AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)), sinv.outstanding_amount,0)) `ninety`
			 ,SUM(IF(DATE(sinv.posting_date) < DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)),'%Y-%m-01'), sinv.outstanding_amount,0)) `more`
			 ,SUM(sinv.outstanding_amount) `total`
			FROM `tabPurchase Invoice` sinv
			WHERE sinv.`docstatus` = 1
			-- AND sinv.`outstanding_amount` > 0
			AND sinv.`supplier` = "{supplier}"
			and sinv.posting_date <= "{posting_date}"
				""".format(supplier=self.supplier,posting_date=self.posting_date), as_dict = 1)


			self.current_amount = out_amount[0].current
			self.days_30 = out_amount[0].thirty
			self.days_60 = out_amount[0].sixty
			self.days_90 = out_amount[0].ninety
			self.days_120 = out_amount[0].more

			self.total_amount = out_amount[0].total