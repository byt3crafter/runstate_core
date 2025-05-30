from . import __version__ as app_version

app_name = "impex"
app_title = "Impex"
app_publisher = "Yousef Restom"
app_description = "Impex Customizations"
app_email = "youssef@totrox.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/impex/css/impex.css"
app_include_js = ["impex.bundle.js"]

# include js, css files in header of web template
# web_include_css = "/assets/impex/css/impex.css"
# web_include_js = "/assets/impex/js/impex.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "impex/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Purchase Invoice": "public/js/purchase_invoice.js",
	"Item": "public/js/item.js",
	"Purchase Order": "public/js/purchase_order.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "impex.utils.jinja_methods",
# 	"filters": "impex.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "impex.install.before_install"
# after_install = "impex.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "impex.uninstall.before_uninstall"
# after_uninstall = "impex.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "impex.utils.before_app_install"
# after_app_install = "impex.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "impex.utils.before_app_uninstall"
# after_app_uninstall = "impex.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "impex.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

permission_query_conditions = {
	"Supplier": "impex.extends.supplier.get_permission_query_conditions",
	"Impex Settings": "impex.impex.doctype.impex_settings.impex_settings.get_permission_query_conditions",
}

has_permission = {
	"Supplier": "impex.extends.supplier.has_permission",
	"Impex Settings": "impex.impex.doctype.impex_settings.impex_settings.has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

override_doctype_class = {
    "Sales Order": "impex.extends.sales_order.CustomSalesOrder"
}

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    # "Sales Order": {
    #     "validate": "impex.extends.sales_order.validate",
    # },
    "Supplier Quotation": {
        "on_submit": "impex.extends.supplier_quotation.on_submit",
    },
    "Pick List": {
        "validate": "impex.extends.pick_list.validate",
    },
    # "Purchase Invoice": {
    #     "on_submit": "impex.extends.purchase_invoice.on_submit",
    # },
    "Purchase Order": {
        "validate": "impex.extends.purchase_order.validate",
        "on_submit": [
            "impex.extends.purchase_order.on_submit",
            "impex.extends.purchase_invoice.on_submit",
        ],
    },
    "Purchase Receipt": {
        "on_submit": "impex.extends.purchase_receipt.on_submit",
        "on_cancel": "impex.extends.purchase_receipt.on_cancel"
    },
    "Sales Invoice": {
		"autoname": "impex.extends.sales_invoice.autoname",
		"on_submit": "impex.extends.sales_invoice.on_submit"
	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    # "all": [
    # 	"impex.tasks.all"
    # ],
    # "daily": ["impex.extends.sales_order.update_sales_orders_prices"],
    "hourly": ["impex.extends.sales_order.update_sales_orders_prices"],
    # "weekly": [
    # 	"impex.tasks.weekly"
    # ],
    # "monthly": [
    # 	"impex.tasks.monthly"
    # ],
    "cron": {"0 21 * * 0": "impex.tasks.weekly"},
}

# Testing
# -------

# before_tests = "impex.install.before_tests"

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
    "erpnext.controllers.queries.item_query": "impex.extends.queries.item_query",
    "frappe.desk.search.search_link": "impex.extends.search.search_link",
}

standard_queries = {
    "Item": "impex.extends.queries.item_query",
}

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "impex.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["impex.utils.before_request"]
# after_request = ["impex.utils.after_request"]

# Job Events
# ----------
# before_job = ["impex.utils.before_job"]
# after_job = ["impex.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"impex.auth.validate"
# ]


fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            [
                "name",
                "in",
                [
                    "Item Barcode-barcode_image",
                    "Purchase Receipt Item-custom_label_qty",
                    "Sales Invoice-custom_special_order",
                    "Sales Order-custom_special_order",
                    "Purchase Order-custom_special_order",
                    "Purchase Invoice-custom_special_order",
                    "Supplier-exchange_rate",
                    "Pick List Item-custom_bin_location",
                    "Supplier-rules_to_update_prices",
                    "Supplier-rule_prices",
                    "Item-rules_to_update_prices",
                    "Item-rule_prices",
                    "Item Group-rules_to_update_prices",
                    "Item Group-rule_prices",
                    "Item-part_1",
                    "Item-part_2",
                    "Item-part_3",
                    "Item-part_4",
                    "Item-part_5",
                    "Item-part_6",
                    "Item-part_7",
                    "Item-part_8",
                    "Item-part_9",
                    "Item-part_10",
                    "Item-special_parameter",
                    "Item-cb_plu",
                    "Purchase Order Item-custom_part_number",
                    "Purchase Receipt Item-custom_part_number",
                    "Purchase Order-custom_dont_regenerate_in_draft",
                    "Sales Order Item-custom_inter_company_purchase",
                    "Sales Order Item-custom_branch_purchase_order",
                    "Sales Order Item-custom_column_break_idb1m",
                    "Sales Order Item-custom_branch_purchase_order_item",
                    "Sales Invoice Item-custom_branch_purchase_order_item",
                    "Sales Invoice Item-custom_column_break_lnulu",
                    "Sales Invoice Item-custom_branch_purchase_order",
                    "Sales Invoice Item-custom_inter_company_purchase",
                    "Sales Invoice-custom_purchase_order_receipt",
                    "Sales Invoice-custom_column_break_fzrxb",
                    "Sales Invoice-custom_receipt_status",
                    "Sales Invoice-custom_receipt_date",
                    "Sales Invoice-custom_received_by",
                    "Delivery Note Item-custom_inter_company_purchase",
                    "Delivery Note Item-custom_branch_purchase_order",
                    "Delivery Note Item-custom_column_break_u6ssy",
                    "Delivery Note Item-custom_branch_purchase_order_item",
                    "Purchase Order-custom_create_sales_order",
                    "Item Supplier-custom_preffered_supplier",
                    "Purchase Receipt-custom_inter_company_invoice_reference",
                    "Purchase Receipt Item-custom_delivery_note"
                ],
            ]
        ],
    },
    {"dt": "Print Format", "filters": [["name", "in", ["Bcode Item", "LTH Labels"]]]},
    {
        "dt": "Client Script",
        "filters": [["name", "in", ["Item-Form", "Purchase Receipt Barcode"]]],
    },
]
