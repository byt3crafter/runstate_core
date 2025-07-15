<template>
	<div class="section-body">
	  <div class="frappe-card p-4">
		<div class="d-flex align-items-center mb-4">
		  <!-- <label class="me-3 fw-bold">Receiving Company</label> -->
		  <!-- Container for the Frappe Link field -->
		  <div class="w-25 me-3" ref="companyFieldContainer"></div>
		  <button @click="loadInvoices" class="btn btn-primary" style="margin-left: 25px;">Load Invoices</button>
		</div>
	  </div>
	  <div class="row mt-4 initialy-hide">
		<div class="col-md-6">
		  <div class="frappe-card p-3">
			<div class="col-md-12 d-flex" style="padding: 0px;">
				<div class="col-md-6" style="padding: 0px;">
					<h2 class="h6 fw-bold mb-3">Invoices</h2>
				</div>
				<div class="col-md-6" style="padding: 0px;">
					<h2 class="h6 fw-bold mb-3" style="text-align: right;">No. of Items</h2>
				</div>
			</div>
			<div
			  v-for="invoice in invoices"
			  :key="invoice.id"
			  class="d-flex align-items-center"
			  @click="selectInvoice(invoice.name)"
			  style="margin: 20px;"
			>
			  <input
				type="checkbox"
				:value="invoice.name"
				@change="updateSelectedInvoices(invoice.name)"
				class="form-check-input me-2"
				:checked="selectedInvoice === invoice.name"
			  />
			  <div style="margin-left: 10px; width: 97%;">
				<p class="fw-bold mb-0">{{ invoice.name }}</p>
				<p class="text-muted small">{{ invoice.date }}</p>
			  </div>
			  <p class="fw-bold" style="text-align: right;">{{ invoice.item_qty }}</p>
			</div>
		  </div>
		</div>
  
		<div class="col-md-6">
		  <div class="frappe-card p-3">
			<div class="col-md-12 d-flex" style="padding: 0px;">
				<div class="col-md-6" style="padding: 0px;">
					<h2 class="h6 fw-bold mb-3">Items</h2>
				</div>
				<div class="col-md-6" style="padding: 0px;">
					<h2 class="h6 fw-bold mb-3" style="text-align: right;">Qty</h2>
				</div>
			</div>
			<div
			  v-for="item in items"
			  :key="item.code"
			  class="d-flex justify-content-between"
			>
			  <div>
				<p class="fw-bold mb-0">{{ item.item_code }}</p>
				<p class="text-muted small">{{ item.item_name }}</p>
			  </div>
			  <p class="fw-bold">{{ item.qty }}</p>
			</div>
		  </div>
		  <button @click="confirmReceipt" class="btn btn-primary d-block mx-auto mt-4">
				Confirm Items Receipt
		  </button>
		</div>
	  </div>
	</div>
  </template>
  
  <script>
  export default {
	data() {
	  return {
		branch: "",
		invoices: [],
		invoiceItems: {},
		selectedInvoices: [],
		items: [],
		companyField: null,
		selectedInvoice: ''
	  };
	},
	mounted() {
	  // Instantiate a Frappe Link field for Company using make_control
	  let me = this;
	  this.companyField = frappe.ui.form.make_control({
		parent: this.$refs.companyFieldContainer,
		df: {
		  fieldname: "company",
		  label: "Company",
		  fieldtype: "Link",
		  options: "Company",
		  default: this.branch,
		  change: function(){
			me.branch = me.companyField.get_value();
		  }
		},
		render_input: true
	  });
	},
	methods: {
	  loadInvoices() {
		frappe.call({
			method: "impex.impex.page.invoice_receipt.invoice_receipt.get_invoices",
			freeze: true,
			args: {
				company: this.branch
			},
			callback: (response) => {
				console.log("Response: ", response);
				if (response.message) {
					this.invoices = response.message.invoices;
					this.invoiceItems = response.message.items;
					document.querySelectorAll('.initialy-hide').forEach(element => {
						element.style.display = 'flex';
					});
				}
			}
		});
	  },
	  selectInvoice(invoiceName) {
		this.items = this.invoiceItems[invoiceName];
	  },
	  updateSelectedInvoices(invoiceName) {
			// const index = this.selectedInvoices.indexOf(invoiceName);
			// if (index > -1) {
			// 	this.selectedInvoices.splice(index, 1);
			// } else {
			// 	this.selectedInvoices.push(invoiceName);
			// }
			this.selectedInvoice = invoiceName;
	  },
	  confirmReceipt() {
		let me = this;
		frappe.call({
			method: "impex.impex.page.invoice_receipt.invoice_receipt.confirm_receipt",
			args: {
				"invoices": [me.selectedInvoice]
			},
			freeze: true,
			callback: function(res){
				if(res.message){
					frappe.msgprint("Invoices received: " + res.message.join(", "));
					me.invoices = [];
					me.items = [];
					me.loadInvoices();
				}
			}
		});
	  }
	}
  };
  </script>
  
  <style>
  /* .frappe-card {
	background: #fff;
	border: 1px solid #d1d8dd;
	border-radius: 4px;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  } */

  .list-group-item {
	border-top: none;
	border-right: none;
	border-left: none;
  }

  .initialy-hide {
	display: none;
  }
  </style>
  