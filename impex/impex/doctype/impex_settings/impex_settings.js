// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Impex Settings", {
  refresh: function(frm) {
	frm.set_query("default_warehouse", "default_company_settings", function(doc, cdt, cdn) {
		var row = locals[cdt][cdn];
		return {
			filters: {
				'company': row.company
			}
		};
	});

	frm.set_query("main_company_warehouse",  function(){
		return {
			filters: {
				"company": frm.doc.main_company
			}
		}
	});

	frm.set_query("tax_template", "default_company_settings", function(doc, cdt, cdn) {
		var row = locals[cdt][cdn];
		return {
			filters: {
				'company': row.company
			}
		};
	});

	frm.set_query("tax_template",  function(){
		return {
			filters: {
				"company": frm.doc.main_company
			}
		}
	});

	frm.set_query("sales_tax_template",  function(){
		return {
			filters: {
				"company": frm.doc.main_company
			}
		}
	});
  },

  create_pick_list: function (frm) {
    frappe.call({
      method: "impex.extends.sales_order.background_generate_pick_lists",
      callback: function (r) {
        frappe.msgprint("Pick List is processing in the background");
      },
    });
  },

  update_sales_orders_prices: function (frm) {
    frappe.call({
      method: "impex.extends.sales_order.background_update_sales_orders_prices",
      callback: function (r) {
        frappe.msgprint("Prices are being updated in the background");
      },
    });
  },
});
