// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order Generator", {
  onload: function(frm) {
    if(frm.doc.__islocal){
		frm.trigger('check_po_in_draft');
	}
  },

  company: function(frm) {
	frm.trigger('check_po_in_draft');
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
  },
});
