// Copyright (c) 2024, Yousef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("Price Change", {
  refresh: function (frm, cdt, cdn) {
    cur_frm.fields_dict.rule_prices.$wrapper
      .find(".grid-body .rows")
      .find(".grid-row")
      .each(function (i, item) {
        let d =
          locals[cur_frm.fields_dict["rule_prices"].grid.doctype][
            $(item).attr("data-name")
          ];
        if (d.new_rate != d.last_rate) {
          $(item).find(".grid-static-col").css({ color: "#FF0000" });
        }
      });
    frm.refresh_field("rule_prices");
  },
});
