<template>
	<div class="section-body">
	  <div class="frappe-card p-4">
		<div class="d-flex align-items-center mb-4 field-container">
		  <div class="w-25 me-3" ref="companyFieldContainer"></div>
		  <div class="w-25 me-3" ref="fromDateContainer"></div>
		  <div class="w-25 me-3" ref="toDateContainer"></div>
  
		  <!-- Load Invoices Button -->
		  <button @click="loadInvoices" class="btn btn-primary" style="margin-left: 25px;">Load Invoices</button>
		</div>
	  </div>
  
	  <!-- Search Field -->
	  <div v-if="invoices.length > 1" class="mb-4 search-container">
		<div class="col-md-6">
		  <input
			v-model="searchQuery"
			type="text"
			class="form-control"
			placeholder="Search Invoice"
			@input="filterInvoices"
		  />
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
			  v-for="invoice in filteredInvoices"
			  :key="invoice.id"
			  class="d-flex align-items-center"
			  @click="canSelectMultiple ? updateSelectedInvoices(invoice.name) : selectInvoice(invoice.name)"
			  style="margin: 20px;"
			>
			  <input
				type="checkbox"
				:value="invoice.name"
				@change="updateSelectedInvoices(invoice.name)"
				class="form-check-input me-2"
				:checked="canSelectMultiple ? selectedInvoices.includes(invoice.name) : selectedInvoice === invoice.name"
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
		filteredInvoices: [],
		invoiceItems: {},
		selectedInvoices: [],
		items: [],
		companyField: null,
		selectedInvoice: '',
		fromDateField: null,
		toDateField: null,
		fromDate: frappe.datetime.get_today(),
		toDate: frappe.datetime.get_today(),
		searchQuery: '',
		canSelectMultiple: false
	  };
	},
	mounted() {
	  let me = this;

	  // Check if the user can select multiple invoices
	  frappe.call({
		method: "impex.impex.page.invoice_receipt.invoice_receipt.can_select_multiple_invoices",
		freeze: true,
		callback: (response) => {
		  me.canSelectMultiple = response.message; // Set the flag based on the response
		},
	  });

	  // Instantiate the Company field
	  this.companyField = frappe.ui.form.make_control({
		parent: this.$refs.companyFieldContainer,
		df: {
		  fieldname: "company",
		  label: "Company",
		  fieldtype: "Link",
		  options: "Company",
		  default: this.branch,
		  change: function () {
			me.branch = me.companyField.get_value();
		  },
		},
		render_input: true,
	  });

	  // Instantiate the From Date field
	  this.fromDateField = frappe.ui.form.make_control({
		parent: this.$refs.fromDateContainer,
		df: {
		  fieldname: "from_date",
		  label: "From Date",
		  fieldtype: "Date",
		  change: function () {
			me.fromDate = me.fromDateField.get_value();
		  },
		},
		render_input: true,
	  });

	  // Set the default value for From Date
	  this.fromDateField.set_value(this.fromDate);

	  // Instantiate the To Date field
	  this.toDateField = frappe.ui.form.make_control({
		parent: this.$refs.toDateContainer,
		df: {
		  fieldname: "to_date",
		  label: "To Date",
		  fieldtype: "Date",
		  change: function () {
			me.toDate = me.toDateField.get_value();
		  },
		},
		render_input: true,
	  });

	  // Set the default value for To Date
	  this.toDateField.set_value(this.toDate);
	},
	methods: {
	  loadInvoices() {
		// Validate that branch, fromDate, and toDate are set
		if (!this.branch) {
		  frappe.msgprint({
			title: __("Validation Error"),
			message: __("Please select a company."),
			indicator: "red",
		  });
		  return;
		}
	
		if (!this.fromDate || !this.toDate) {
		  frappe.msgprint({
			title: __("Validation Error"),
			message: __("Please select both From Date and To Date."),
			indicator: "red",
		  });
		  return;
		}
	
		// Validate that toDate is not before fromDate
		if (frappe.datetime.str_to_obj(this.toDate) < frappe.datetime.str_to_obj(this.fromDate)) {
		  frappe.msgprint({
			title: __("Validation Error"),
			message: __("To Date cannot be earlier than From Date."),
			indicator: "red",
		  });
		  return;
		}
	
		// Proceed with loading invoices if validation passes
		frappe.call({
		  method: "impex.impex.page.invoice_receipt.invoice_receipt.get_invoices",
		  freeze: true,
		  args: {
			company: this.branch,
			from_date: this.fromDate,
			to_date: this.toDate,
		  },
		  callback: (response) => {
			console.log("Response: ", response);
			if (response.message) {
			  this.invoices = response.message.invoices;
			  this.filteredInvoices = this.invoices; // Initialize filteredInvoices
			  this.invoiceItems = response.message.items;
			  document.querySelectorAll(".initialy-hide").forEach((element) => {
				element.style.display = "flex";
			  });
			}
		  },
		});
	  },
	  selectInvoice(invoiceName) {
		this.items = this.invoiceItems[invoiceName];
	  },
	  updateSelectedInvoices(invoiceName) {
		if (this.canSelectMultiple) {
		  if (this.selectedInvoices.includes(invoiceName)) {
			// Remove the invoice if already selected
			this.selectedInvoices = this.selectedInvoices.filter((name) => name !== invoiceName);
		  } else {
			// Add the invoice to the selected list
			this.selectedInvoices = [...this.selectedInvoices, invoiceName]; // Ensure reactivity
		  }
		} else {
		  this.selectedInvoice = invoiceName;
		}
	  },
	  confirmReceipt() {
		let me = this;
		const invoicesToReceive = this.canSelectMultiple ? this.selectedInvoices : [this.selectedInvoice];
	
		if (invoicesToReceive.length === 0) {
		  frappe.msgprint({
			title: __("Validation Error"),
			message: __("Please select at least one invoice."),
			indicator: "red",
		  });
		  return;
		}
	
		frappe.call({
		  method: "impex.impex.page.invoice_receipt.invoice_receipt.confirm_receipt",
		  args: {
			invoices: invoicesToReceive,
		  },
		  freeze: true,
		  callback: function (res) {
			if (res.message) {
			  frappe.msgprint("Invoices received: " + res.message.join(", "));
			  me.invoices = [];
			  me.items = [];
			  me.loadInvoices();
			}
		  },
		});
	  },
	  filterInvoices() {
		const query = this.searchQuery.toLowerCase();
		this.filteredInvoices = this.invoices.filter(invoice =>
		  invoice.name.toLowerCase().includes(query)
		);
	  }
	}
  };
  </script>
  
  <style>
  .list-group-item {
	border-top: none;
	border-right: none;
	border-left: none;
  }

  .initialy-hide {
	display: none;
  }

  .search-container {
	background-color: #ffffff; 
	padding: 15px;
	margin-top: 21px;
	border-radius: 5px;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); /* Optional: Add a subtle shadow */
  }

  .field-container {
	gap: 15px; /* Adds space between fields */
  }
  
  @media (max-width: 768px) {
	.field-container {
	  flex-wrap: wrap; /* Stack fields on smaller screens */
	  gap: 10px;
	}
  }
  </style>
