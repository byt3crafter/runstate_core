from frappe import _

def get_data():
	return {
		"internal_links": {
			"Purchase Order": ["items", "po"]
		},
		# "transactions": [
		# 	{
		# 		"label": "Transactions",
		# 		"items": [
		# 			"Purchase Order"
		# 		]
		# 	}
		# ]
	}