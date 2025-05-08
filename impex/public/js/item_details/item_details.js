import ItemDetails from "./ItemDetails.vue"
frappe.provide("impex.item_details");

impex.item_details.ItemDetails = class {
	constructor(wrapper, item_code) {
		console.log("item Code: ", item_code);
		this.wrapper = wrapper;
		this.item_code = item_code;
		this.make_body();
	}

	make_body(){
		new Vue({
			el: this.wrapper,
			render: (h) => h(ItemDetails, {
				props: {
					itemCode: this.item_code
				}
			})
		});
	}
}