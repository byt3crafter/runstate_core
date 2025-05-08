<template>
	<div class="container border p-4 my-4">
	  <!-- Top Info -->
	  <div class="row mb-3">
		<div class="col-md-6">
		  <p><strong>Item Code:</strong> {{ item_code }}</p>
		  <p><strong>Description:</strong> {{ description }}</p>
		  <p><strong>Item Group:</strong> {{ item_group }}</p>
		</div>
		<div class="col-md-6">
		  <p><strong>Supplier:</strong> {{ supplier }}</p>
		  <p><strong>Bin Location:</strong> {{ bin_location }}</p>
		</div>
	  </div>
  
	  <!-- Stock & Prices -->
	  <div class="row mb-3">
		<div class="col-md-6">
		  <p><strong>Total Sold:</strong> {{ total_sold }}</p>
		  <p><strong>Total Purchase:</strong> {{ total_purchased }}</p>
		  <p><strong>Current Stock:</strong> {{ current_stock }}</p>
		</div>
		<div class="col-md-6">
		  <p><strong>Cost:</strong> {{ cost }}</p>
		  <p v-for="price in selling_prices">
			<strong>{{ price.price_list }}: </strong>{{ price.price }} ({{ price.percent_diff }}%)
		  </p>
		</div>
	  </div>
  
	  <!-- Summary Table -->
	  <div class="table-responsive mb-4">
		<table class="table table-bordered text-center">
		  <thead class="table-light">
			<tr>
			  <th>Company</th>
			  <th v-for="company in user_companies" :key="company">{{ company }}</th>
			</tr>
		  </thead>
		  <tbody>
			<tr>
				<th>B/O Sales:</th>
				<td v-for="company in user_companies" :key="company">
					{{ companies_details[company].bo_sales }}
				</td>
			</tr>
			<tr>
				<th>B/O Purch:</th>
				<td v-for="company in user_companies" :key="company">
					{{ companies_details[company].bo_purchase }}
				</td>
			</tr>
			<tr>
				<th>In Stock:</th>
				<td v-for="company in user_companies" :key="company">
					{{ companies_details[company].in_stock }}
				</td>
			</tr>
			<tr>
				<th>4M Average:</th>
				<td v-for="company in user_companies" :key="company">
					{{ companies_details[company].four_months_average}}
				</td>
			</tr>
			<tr>
				<th>Total 12M:</th>
				<td v-for="company in user_companies" :key="company">
					{{ companies_details[company].twelve_months_sales}}
				</td>
			</tr>
			<!-- <tr v-for="row in summary.rows" :key="row.label">
			  <th class="text-start">{{ row.label }}</th>
			  <td v-for="(val, idx) in row.values" :key="idx">{{ val }}</td>
			  <td v-for="company in summary.companies" :key="company">{{ val }}</td>
			</tr> -->
		  </tbody>
		</table>
	  </div>
  
	  <!-- Monthly Sales Table -->
	  <div class="table-responsive mb-4">
		<table class="table table-bordered text-center">
		  <thead class="table-light">
			<tr>
			  <th>Months</th>
			  <th v-for="(value, key) in monthlySales" :key="key">{{ key }}</th>
			</tr>
		  </thead>
		  <!-- <thead class="table-light">
			<tr>
			  <th v-for="header in monthlySales.headers" :key="header">{{ header }}</th>
			</tr>
		  </thead>
		  <tbody>
			<tr v-for="row in monthlySales.rows" :key="row.id">
			  <td v-for="(val, idx) in row.values" :key="idx">{{ val }}</td>
			</tr>
		  </tbody> -->
		  <tbody>
			<tr>
			  <th>Sold</th>
			  <td v-for="(value, key) in monthlySales" :key="key">{{ value }}</td>
			</tr>
			<tr>
			  <th>Received</th>
			  <td v-for="(value, key) in monthlyPurchases" :key="key">{{ value }}</td>
			</tr>
		  </tbody>
		</table>
	  </div>
  
	  <!-- Image and Cost History -->
	  <div class="row">
		<div class="col-md-4 d-flex align-items-center justify-content-center border" style="height: 200px;">
		  <img :src="image" class="img-fluid" alt="Item Image" />
		</div>
		<div class="col-md-8">
			<div class="table-responsive cost-history-container">
				<table class="table table-bordered text-center">
					<thead class="table-light sticky-header">
					<tr>
						<th>Cost</th>
						<th>Supplier</th>
						<th>Date</th>
						<th>Doc</th>
					</tr>
					</thead>
					<tbody @scroll="handleScroll" ref="costHistoryTable">
					<tr v-for="(entry, idx) in costHistory" :key="idx">
						<td>{{ entry.cost }}</td>
						<td>{{ entry.supplier }}</td>
						<td>{{ entry.date }}</td>
						<td>
							<a :href="entry.doc_url" target="_blank" rel="noopener noreferrer">{{ entry.doc }}</a>
						</td>
					</tr>
					<tr v-if="isLoading">
						<td colspan="4" class="text-center">
						<div class="spinner-border text-primary" role="status">
							<span class="visually-hidden">Loading...</span>
						</div>
						</td>
					</tr>
					</tbody>
				</table>
			</div>
		</div>
	  </div>
	</div>
  </template>
  
  <script>
  export default {
	name: "ItemDetails",
	props: {
		itemCode: {
			type: String,
			required: true,
		},
	},
	data() {
	  return {
		item_code: "",
		description: "",
		item_group: "",
		supplier: "",
		bin_location: "",
		total_sold: 0,
		total_purchased: 0,
		current_stock: 0,
		cost: 0,
		selling_prices: [],
		sell_price_1: 0,
		sell_price_2: 0,
		sell_price_3: 0,
		image: "",
		user_companies: [],
		companies_details: {},
		monthlySales: {},
		monthlyPurchases: {},
		costHistory: [],
		page: 1,
		isLoading: false,
		hasMore: true,
	  };
	},

	mounted() {
		this.fetchItemDetails();
		this.loadCostHistory();
	},

	methods: {
		async fetchItemDetails() {
			try {
				const response = await frappe.call({
					method: 'impex.extends.item.get_item_details',
					args: { item_code: this.itemCode },
				});
				if (response.message) {
					console.log("Item Details: ", response.message);
					Object.keys(response.message).forEach(key => {
						if (this.hasOwnProperty(key)) {
							this[key] = response.message[key];
						}
					});

					this.user_companies = response.message.company_details.companies;
					this.companies_details = response.message.company_details.companies_details
					this.monthlySales = response.message.monthly_sales;
					this.monthlyPurchases = response.message.monthly_purchases;
				}
			} catch (error) {
				console.error('Error fetching item details:', error);
			}
		},

		async loadCostHistory() {
			if (this.isLoading || !this.hasMore) return;

			this.isLoading = true;
			try {
				const response = await frappe.call({
				method: 'impex.extends.item.get_cost_history',
				args: {
					item_code: this.itemCode,
					page: this.page,
					page_size: 20
				}
				});

				if (response.message) {
				const newEntries = response.message.entries;
				this.costHistory = [...this.costHistory, ...newEntries];
				this.hasMore = response.message.has_more;
				this.page += 1;
				}
			} catch (error) {
				console.error('Error loading cost history:', error);
			} finally {
				this.isLoading = false;
			}
		},

		handleScroll(event) {
			const target = event.target;
			const bottom = target.scrollHeight - target.scrollTop === target.clientHeight;
			
			if (bottom && !this.isLoading) {
				this.loadCostHistory();
			}
		},
	},
  };
</script>
  
<style scoped>
  img {
	max-height: 180px;
  }

  .cost-history-container {
	height: 300px;
	overflow-y: auto;
  }

  .sticky-header {
	position: sticky;
	top: 0;
	background: white;
	z-index: 1;
  }
</style>