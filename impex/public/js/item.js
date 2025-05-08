frappe.ui.form.on("Item", {
	refresh: function(frm){
		// Add item details button
		frm.add_custom_button(__('Item Details'), function () {
			frm.events.launch_item_details_popup(frm);
		});

		// Create or clear an existing section for Bin data
		let section = frm.dashboard.add_section("", __("Bin Locations"));

		// Get bins related to the current item
		if (frm.doc.item_code) {
		  frappe.call({
			method: "impex.extends.item.get_bin_locations",
			args: {
				item_code: frm.doc.item_code
			},
			callback: function(r) {
			  if (r.message && r.message.length) {
				let rows = r.message
				  .map(bin => {
					return `
						<div class="row" style="padding-bottom: 10px;">
							<div class="col-sm-4">
								<a data-type="warehouse">${bin.warehouse}</a>
							</div>
							<div class="col-sm-4">
								<a data-type="bin-location">${bin.location}</a>
							</div>
							<div class="col-sm-4">
								<button class="btn btn-default btn-xs btn-move" 
									data-warehouse="${bin.warehouse}"
									data-location="${bin.location}">
										Change Location
								</button>
							</div>
						</div>
					`;
				  })
				  .join("");
				
				let html = `
					  ${rows}
				`;
				section.empty(); // Clear existing content if any
				section.html(html); // Insert the table into the section body
			  } else {
				section.html(`<center>${__("No bin location data found for this Item.")}</center>`);
			  }
			  frm.events.change_location_button(frm, section);
			}
		  });
		} else {
		  section.html(__("Please save the Item to see Warehouse Bin location data."));
		}
	},

	change_location_button: function(frm, section) {
		console.log("Section: ", section);
		console.log("btn-move", section.find(".btn-move"));
		section.find(".btn-move").on('click', function() {
			// let $row = $(this).closest('.row');
			// let warehouse = $row.find('a[data-type="warehouse"]').text();
			// let current_location = $row.find('a[data-type="bin-location"]').text();
			let warehouse = $(this).data('warehouse');
			let current_location = $(this).data('location');

			let d = new frappe.ui.Dialog({
				title: __('Change Bin Location'),
				fields: [
					{
						label: 'Warehouse',
						fieldname: 'warehouse',
						fieldtype: 'Link',
						options: 'Warehouse',
						default: warehouse,
						read_only: 1
					},
					{
						label: 'Current Location',
						fieldname: 'current_location',
						fieldtype: 'Link',
						options: 'Bin Location',
						default: current_location,
						read_only: 1
					},
					{
						label: 'New Location',
						fieldname: 'new_location',
						fieldtype: 'Link',
						options: 'Bin Location',
						reqd: 1
					}
				],
				primary_action_label: __('Save'),
				primary_action(values) {
					// Handle the save action here
					frappe.call({
						method: 'impex.extends.item.update_bin_location',
						args: {
							item_code: frm.doc.item_code,
							warehouse: values.warehouse,
							new_location: values.new_location
						},
						callback: function(r) {
							if (r.message) {
								frappe.msgprint(__('Bin location updated successfully.'));
								d.hide();
								frm.refresh();
							}
						}
					});
				}
			});

			d.show();
		});
	},

	launch_item_details_popup: function (frm) {
		// Create a dialog to host the Vue component
		const dialog = new frappe.ui.Dialog({
		  title: __('Item Details'),
		  size: 'extra-large',
		  fields: [
			{
			  fieldtype: 'HTML',
			  fieldname: 'vue_container',
			},
		  ],
		});

		const wrapper = dialog.fields_dict.vue_container.$wrapper[0];
		console.log("Wrapper before: ", wrapper);
		wrapper.invoice_receipt = new impex.item_details.ItemDetails(wrapper, frm.doc.item_code);
		dialog.show()
	}

});