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

  update_item_prices: function(frm){
    frappe.call({
      method: "impex.impex.doctype.price_change.price_change.recalculate_zero_rated_item_prices",
        freeze: true,
        callback: function (r) {
          console.log(r);
        },
    });
  },

  btn_sync_items: function(frm){
    frappe.call({
      method: "impex.impex.api.items_sync.sync_items_to_servers",
      freeze: true,
      freeze_message: "Syncing",
      callback: function(r) {
        const res = r.message || {};
        const status = (res.status || 'unknown').toLowerCase();
        const text = res.message || '';
        const indicator = status === 'failed' ? 'red' : status === 'queued' ? 'orange' : 'green';

        frappe.msgprint({
          title: __('Item Sync'),
          message: `${__('Status')}: ${frappe.utils.escape_html(status)}<br>${frappe.utils.escape_html(text)}`,
          indicator
        });
      }
    })
  }
});
