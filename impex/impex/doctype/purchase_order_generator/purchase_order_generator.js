// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Order Generator", {
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
