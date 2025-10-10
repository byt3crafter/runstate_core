{% include 'impex/public/js/rule_prices.js' %}

frappe.ui.form.on("Item Group", {
    refresh(frm) {
        if (!frm.is_new()) {
            impex.rule_prices.setup(frm, { html_field: 'custom_rule_prices_html' });
        }
    }
});