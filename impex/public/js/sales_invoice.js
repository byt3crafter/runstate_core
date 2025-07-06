frappe.ui.form.on("Sales Invoice", {
	onload: function(frm) {
		if(frm.doc.__islocal && !(frm.doc.items && frm.doc.items.length > 0 
			&& frm.doc.items[0].delivery_note && frm.doc.items[0].delivery_note != "")){
			frm.set_value("update_stock", 1);
		}
	}
});