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
	},

	company: function(frm){
		frm.set_value("custom_create_sales_order", (main_company != frm.doc.company));
	}
});