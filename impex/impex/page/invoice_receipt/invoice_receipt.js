frappe.provide("impex.invoice_receipt");
frappe.pages['invoice-receipt'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Invoice Receipt',
		single_column: true
	});
	console.log("App: ", this.page);
	wrapper.invoice_receipt = new impex.invoice_receipt.InvoiceReceipt(wrapper);
}