import Home from "./home.vue";
frappe.provide('impex.invoice_receipt');

impex.invoice_receipt.InvoiceReceipt = class {
	// constructor({ parent }) {
	// 	console.log("Parent: ", parent);
	// 	console.log("Document: ", $(document));
    //     this.$parent = $(document);
    //     this.page = parent.page;
    //     this.make_body();
    // }

	constructor(wrapper) {
		console.log("Wrapper: ", wrapper);
		this.wrapper = $(wrapper).find(".layout-main-section");
		this.page = wrapper.page;
		this.make_body();
	}

	make_body() {
		console.log("Wrapper Body: ", this.wrapper);
		console.log("Wrapper Page: ", this.page);
		new Vue({
			el: this.wrapper[0],
			render: (h) => h(Home, {
				// props: {
				// 	doc: this.doc
				// }
			})
		});
	}
}