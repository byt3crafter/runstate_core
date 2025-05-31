frappe.ui.form.on("Sales Invoice", {
	onload: function(frm) {
		if(frm.doc.__islocal){
			frm.set_value("update_stock", 1);
		}
	}
});