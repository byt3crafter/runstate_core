// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Impex Settings", {
  // refresh: function(frm) {

  // }

  create_pick_list: function (frm) {
    frappe.call({
      method: "impex.extends.sales_order.background_generate_pick_lists",
      callback: function (r) {
        frappe.msgprint("Pick List is processing in the background");
      },
    });
  },
});
