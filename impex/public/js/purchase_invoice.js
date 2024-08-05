// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
  refresh: function (frm) {
    // add custom button
    if (frm.doc.docstatus == 1) {
      frm.add_custom_button(__("Create Price Change"), function () {
        frappe.call({
          method:
            "impex.impex.doctype.price_change.price_change.create_price_change_from_purchase_invoice",
          args: {
            doctype: frm.doc.doctype,
            doc_name: frm.doc.name,
          },
          callback: function (r) {
            if (r.message) {
              frappe.show_alert({
                message: __("Price Change created successfully"),
                indicator: "green",
              });
            }
          },
        });
      });
    }
  },
});
