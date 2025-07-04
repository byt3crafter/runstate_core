# -*- coding: utf-8 -*-
# Copyright (c) 2021, riconova and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class CustomerStatement(Document):
	
	@frappe.whitelist()
	def get_data(self):
		clause_customer = ""
		if self.customer :
			clause_customer = """ AND sinv.`customer` = "{}" """.format(self.customer)

		if not self.posting_date :
			frappe.throw("Please choose the posting date first")

		self.invoice_list = []

		# ambil data SINV
		get_sinv = frappe.db.sql("""
			SELECT sinv.`name`, sinv.`is_return`, sinv.`posting_date`, sinv.`due_date`, sinv.`outstanding_amount`, sinv.`po_no`, DATEDIFF(sinv.`due_date`, CURDATE()),sinv.grand_total
			FROM `tabSales Invoice` sinv
			LEFT JOIN `tabSales Invoice` pinv ON sinv.return_against = pinv.name AND pinv.outstanding_amount > 0
			WHERE sinv.`docstatus` = 1
			-- AND sinv.`outstanding_amount` > 0
			{}
			AND sinv.`posting_date` <= "{}"
			and (sinv.outstanding_amount > 0 or pinv.name is not null)
			ORDER BY sinv.`posting_date` ASC, sinv.`posting_time` ASC	
		""".format(clause_customer,self.posting_date), as_dict = 1)
		# get_sinv = frappe.db.sql("""
		# 	SELECT sinv.`name`, sinv.`is_return`, sinv.`posting_date`, sinv.`due_date`, sinv.`outstanding_amount`, sinv.`po_no`, DATEDIFF(sinv.`due_date`, CURDATE()) 
		# 	FROM `tabSales Invoice` sinv
		# 	WHERE sinv.`docstatus` = 1
		# 	AND sinv.`outstanding_amount` > 0
		# 	AND sinv.`customer` = "{}"
		# 	AND MONTH(sinv.`posting_date`) = MONTH("{}")
		# 	AND sinv.`posting_date` <= "{}"
		# 	ORDER BY sinv.`posting_date` ASC, sinv.`posting_time` ASC	
		# """.format(self.customer, self.posting_date, self.posting_date))

		if get_sinv :
			total_balance = 0
			for i in get_sinv :

				child = self.append("invoice_list", {})
				child.date = i.posting_date
				if i.is_return == 0 :
					child.doc_type = "Tax Invoice"
				else :
					child.doc_type = "Credit Note"

				child.doc_no = i.name
				child.customer_po = i.po_no

				if i.is_return == 0 :
					child.invoice_amount = i.outstanding_amount
				else :
					child.invoice_amount = 0

				if i.is_return == 0 :
					child.credit_note = 0
				else :
					child.credit_note = i.grand_total

				total_balance += child.invoice_amount + child.credit_note
				
				child.balance = total_balance
				child.due_date = i.due_date
				
			# out_amount = frappe.db.sql("""
			# 		SELECT 
			# 			 SUM(IF(datediff(sinv.due_date,"{posting_date}") between 1 and 30, sinv.outstanding_amount,0)) `current`,
			# 			 SUM(IF(datediff(sinv.due_date,"{posting_date}") between -30 and 0, sinv.outstanding_amount,0)) `thirty`,
			# 			 SUM(IF(datediff(sinv.due_date,"{posting_date}") between -60 and -31, sinv.outstanding_amount,0)) `sixty`,
			# 			 SUM(IF(datediff(sinv.due_date,"{posting_date}") between -90 and -61, sinv.outstanding_amount,0)) `ninety`,
			# 			 SUM(IF(datediff(sinv.due_date,"{posting_date}") < -90, sinv.outstanding_amount,0)) `more`,
			# 			 SUM(sinv.outstanding_amount) `total`
			# 			FROM `tabSales Invoice` sinv
			# 			WHERE sinv.`docstatus` = 1
			# 			AND sinv.`outstanding_amount` > 0
			# 			AND sinv.`customer` = "{customer}"
			# 			and sinv.posting_date <= "{posting_date}"
			# 	""".format(customer=self.customer,posting_date=self.posting_date), as_dict = 1)

			out_amount = frappe.db.sql("""
				SELECT 
				 SUM(IF(sinv.posting_date between DATE_FORMAT("{posting_date}",'%Y-%m-01') and "{posting_date}", sinv.outstanding_amount,0)) `current`
				 -- find previous month total outstanding
				 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -1 MONTH)),'%Y-%m-01') AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -1 MONTH)), sinv.outstanding_amount,0)) `thirty`
				 -- find 2 previous month total outstanding
				 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -2 MONTH)),'%Y-%m-01') AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -2 MONTH)), sinv.outstanding_amount,0)) `sixty`
				 -- find 3 previous month total outstanding
				 ,SUM(IF(sinv.posting_date BETWEEN DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)),'%Y-%m-01') AND LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)), sinv.outstanding_amount,0)) `ninety`
				 ,SUM(IF(DATE(sinv.posting_date) < DATE_FORMAT(LAST_DAY(DATE_ADD("{posting_date}", INTERVAL -3 MONTH)),'%Y-%m-01'), sinv.outstanding_amount,0)) `more`
				 ,SUM(sinv.outstanding_amount) `total`
				FROM `tabSales Invoice` sinv
				WHERE sinv.`docstatus` = 1
				AND sinv.`customer` = "{customer}"
				AND sinv.posting_date <= "{posting_date}"
				""".format(customer=self.customer,posting_date=self.posting_date), as_dict = 1)

			self.current_amount = out_amount[0].current
			self.days_30 = out_amount[0].thirty
			self.days_60 = out_amount[0].sixty
			self.days_90 = out_amount[0].ninety
			self.days_120 = out_amount[0].more

			self.total_amount = out_amount[0].total
