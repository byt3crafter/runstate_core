import frappe

def check_supplier_permission(user):
	if not user:
		user = frappe.session.user
	
	return frappe.has_permission("Supplier", "read", user=user)

def get_permission_query_conditions(user):
	# Override permission based on company for internal supplier
	if not user:
		user = frappe.session.user
	
	# Check if user has Supplier read permission
	if not check_supplier_permission(user):
		return "1=0"  # Return false condition if no permission
	
def has_permission(user=None):
	if not user:
		user = frappe.session.user
	
	# Check if user has Supplier read permission
	if not check_supplier_permission(user):
		return False
	
	return True