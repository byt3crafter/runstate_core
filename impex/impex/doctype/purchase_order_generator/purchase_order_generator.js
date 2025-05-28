// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

let main_company = null;
frappe.ui.form.on("Purchase Order Generator", {
  onload: function(frm) {
    if(frm.doc.__islocal){
		frappe.call({
			method: "frappe.client.get_value",
			args: {
				doctype: "Impex Settings",
				fieldname: "main_company"
			},
			callback: function(r) {
				if (r.message.main_company) {
					main_company = r.message.main_company;
					frm.trigger("company");
				}
			}
		});
	}
  },

  refresh: function(frm){
	frm.set_query("purchase_supplier", "items", function(doc, cdt, cdn){
		return {
			query: "impex.impex.doctype.purchase_order_generator.purchase_order_generator.get_item_suppliers",
			filters: {
				"item_code": locals[cdt][cdn].item_code
			}
		}
	});
  },

  company: function(frm) {
	if(frm.doc.company && frm.doc.company == main_company){
		frm.set_value("inter_company_purchase", 0);
		frm.set_value("orders_in_draft", 1);
		frm.trigger('check_po_in_draft');
	}
	else{
		frm.set_value("inter_company_purchase", 1);
		frm.set_value("orders_in_draft", 0);
	}
  },

  check_po_in_draft: function(frm) {
	frappe.call({
	  method: "impex.impex.doctype.purchase_order_generator.purchase_order_generator.get_po_in_draft",
	  args: {
		company: frm.doc.company
	  },
	  freeze: true,
	  callback: function(r) {
		if (r.message) {
		  frm.set_value("orders_in_draft", r.message);
		}
	  }
	});
  },

  load_items: function (frm) {
    frappe.call({
      doc: frm.doc,
      method: "get_items",
      freeze: true,
      freeze_message: "Loading Items...",
      callback: function (r) {
        frm.refresh_fields();
        // set the doc as dirty to save it
        frm.dirty();
      },
    });
  }
});

frappe.ui.form.on('Purchase Order Generator Items', {
	purchase_supplier: function(frm, cdt, cdn){
		if(locals[cdt][cdn] != ""){
			frappe.call({
				doc: frm.doc,
				method: "get_supplier_rate",
				args: {
					supplier: locals[cdt][cdn].purchase_supplier,
					item_code: locals[cdt][cdn].item_code
				},
				freeze: true,
				freeze_message: "Getting supplier rate",
				callback: function(ret){
					locals[cdt][cdn].purchase_rate = ret.message.purchase_rate;
					locals[cdt][cdn].purchase_currency = ret.message.purchase_currency;
					frm.refresh_fields();
					frm.dirty();
				}
			});
		}
	}
});
