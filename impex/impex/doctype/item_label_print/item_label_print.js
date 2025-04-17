// Copyright (c) 2025, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on('Item Label Print', {
	refresh: function(frm){
		frm.set_query("bin_location", "items", function(doc, cdt, cdn){
			return {
				"query": "impex.impex.doctype.item_label_print.item_label_print.get_bin_locations",
				"filters": {
					"item_code": locals[cdt][cdn].item_code
				}
			}
		});
	},

	load_items: function(frm){
		if(!frm.doc.from_purchase_receipt){
			frappe.msgprint("Please set a Purchase Receipt to get ");
		}
		else {
			frappe.call({
				method: "impex.impex.doctype.item_label_print.item_label_print.get_pr_items",
				args: {
					purchase_receipt: frm.doc.from_purchase_receipt
				},
				freeze: true,
				callback: function(ret){
					if(ret.message.length > 0){
						frm.clear_table("items");
						ret.message.forEach(function(item) {
							frm.add_child("items", item);
						});
						frm.refresh_field("items");
					}
				}
			});
		}
	}
});
