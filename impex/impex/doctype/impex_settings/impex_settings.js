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
    const d = new frappe.ui.Dialog({
      title: __('Sync Items'),
      fields: [
        {
          fieldtype: 'Check',
          fieldname: 'sync_all_items',
          label: __('Sync All Items'),
          default: 0
        },
        {
          fieldtype: 'Check',
          fieldname: 'no_background',
          label: __('Do Not Sync in Background'),
          default: 0,
          description: __('If checked, the sync will run now and block the UI until it finishes.')
        }
      ],
      primary_action_label: __('Start Sync'),
      primary_action: (values) => {
        const full_sync = values.sync_all_items ? 1 : 0;
        const run_in_background = values.no_background ? 0 : 1;

        d.hide();

        frappe.call({
          method: "impex.impex.api.items_sync.sync_items_to_servers",
          args: {
            "full_sync": full_sync,
            "run_in_background": run_in_background
          },
          freeze: true,
          freeze_message: run_in_background ? __('Queuing sync...') : __('Syncing items...')
        }).then(r => {
          const res = r.message || {};
          const status = (res.status || 'unknown').toLowerCase();
          const text = res.message || '';
          const indicator = status === 'failed' ? 'red' : status === 'queued' ? 'orange' : 'green';

          frappe.msgprint({
            title: __('Item Sync'),
            message: `${__('Status')}: ${frappe.utils.escape_html(status)}<br>${frappe.utils.escape_html(text)}`,
            indicator
          });
        }).catch(e => {
          frappe.msgprint({
            title: __('Item Sync'),
            message: `${__('Status')}: failed<br>${frappe.utils.escape_html(e.message || e)}`,
            indicator: 'red'
          });
        });
      }
    });

    d.show();
  },

  sync_suppliers: function(frm) {
    const d = new frappe.ui.Dialog({
      title: __('Sync Suppliers'),
      fields: [
        {
          fieldtype: 'Check',
          fieldname: 'sync_all_suppliers',
          label: __('Sync All Suppliers'),
          default: 0
        },
        {
          fieldtype: 'Check',
          fieldname: 'no_background',
          label: __('Do Not Sync in Background'),
          default: 0,
          description: __('If checked, the sync will run now and block the UI until it finishes.')
        }
      ],
      primary_action_label: __('Start Sync'),
      primary_action: (values) => {
        const full_sync = values.sync_all_suppliers ? 1 : 0;
        const run_in_background = values.no_background ? 0 : 1;

        d.hide();

        frappe.call({
          method: "impex.impex.api.suppliers_sync.sync_suppliers_to_servers",
          args: {
            "full_sync": full_sync,
            "run_in_background": run_in_background
          },
          freeze: true,
          freeze_message: run_in_background ? __('Queuing sync...') : __('Syncing suppliers...')
        }).then(r => {
          console.log("Res: ", r);
          const res = r.message || {};
          const status = (res.status || 'unknown').toLowerCase();
          const text = res.message || '';
          const indicator = status === 'failed' ? 'red' : status === 'queued' ? 'orange' : 'green';

          frappe.msgprint({
            title: __('Supplier Sync'),
            message: `${__('Status')}: ${frappe.utils.escape_html(status)}<br>${frappe.utils.escape_html(text)}`,
            indicator
          });
        }).catch(e => {
          frappe.msgprint({
            title: __('Supplier Sync'),
            message: `${__('Status')}: failed<br>${frappe.utils.escape_html(e.message || e)}`,
            indicator: 'red'
          });
        });
      }
    });

    d.show();
  },

  sync_item_prices: function(frm) {
    const d = new frappe.ui.Dialog({
      title: __('Sync Item Prices'),
      fields: [
        {
          fieldtype: 'Select',
          fieldname: 'sync_mode',
          label: __('What to Sync'),
          options: [
            { label: __('Sync All Supplier Prices'), value: 'all' },
            { label: __('Sync Supplier Prices With Currency'), value: 'currency' }
          ],
          default: 'all',
          reqd: 1
        },
        {
          fieldtype: 'Link',
          fieldname: 'currency',
          label: __('Currency'),
          options: 'Currency',
          depends_on: "eval:doc.sync_mode=='currency'",
          mandatory_depends_on: "eval:doc.sync_mode=='currency'"
        },
        {
          fieldtype: 'Check',
          fieldname: 'no_background',
          label: __('Do Not Sync in Background'),
          default: 0,
          description: __('If checked, the sync will run now and block the UI until it finishes.')
        }
      ],
      primary_action_label: __('Start Sync'),
      primary_action: (values) => {
        const run_in_background = values.no_background ? 0 : 1;

        d.hide();

        frappe.call({
          method: "impex.impex.api.item_price_sync.sync_item_prices_to_servers",
          args: {
            sync_mode: values.sync_mode,
            currency: values.currency || '',
            run_in_background
          },
          freeze: true,
          freeze_message: run_in_background ? __('Queuing sync...') : __('Syncing item prices...')
        }).then(r => {
          const res = r.message || {};
          const status = (res.status || 'unknown').toLowerCase();
          const text = res.message || '';
          const indicator = status === 'failed' ? 'red' : status === 'queued' ? 'orange' : 'green';

          frappe.msgprint({
            title: __('Item Price Sync'),
            message: `${__('Status')}: ${frappe.utils.escape_html(status)}<br>${frappe.utils.escape_html(text)}`,
            indicator
          });
        }).catch(e => {
          frappe.msgprint({
            title: __('Item Price Sync'),
            message: `${__('Status')}: failed<br>${frappe.utils.escape_html(e.message || e)}`,
            indicator: 'red'
          });
        });
      }
    });

    d.show();
  }
});
