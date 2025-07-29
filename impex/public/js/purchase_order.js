let main_company = null;

frappe.ui.form.on("Purchase Order", {
	onload: function(frm){
		if(frm.doc.__islocal){
			frappe.db.get_single_value("Impex Settings", "main_company")
				.then(value => {
					main_company = value;
					frm.trigger("company");
				});
		}

		if(frm.doc.docstatus == 1){
			frm.add_custom_button(__("Create Price Change"), () => {
				frappe.call({
					method: "impex.extends.purchase_order.recreate_manual_price_change",
					args: {
						doctype: frm.doc.doctype,
						docname: frm.doc.name
					},
					freeze: true,
					callback: function(ret){

					}
				});
			});
		}
	},

	company: function(frm){
		frm.set_value("custom_create_sales_order", (main_company != frm.doc.company));
	}
});