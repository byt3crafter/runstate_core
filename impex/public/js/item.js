function make_item_rules_grid() {
    const columns = [
        { key: 'price_list', label: 'Price List', flex: 4 },
        { key: 'margin', label: 'Margin', flex: 2 },
        { key: 'base_price_list', label: 'Base on Price List', flex: 4 }
    ];

    const rows = [];

    const esc = (v) => frappe.utils.escape_html(String(v ?? ''));

    const toolbar = `
        <div class="frappe-control input-max-width" style="margin-bottom:8px;">
            <label class="control-label">${__('For Company')}</label>
            <div class="control-input-wrapper">
                <div class="control-input">
                    <select class="form-control input-sm custom-rule-select">
                        <!-- options will be populated on refresh -->
                    </select>
                </div>
            </div>
        </div>`;

    const header = `
        <div class="grid-heading-row">
            <div class="grid-row">
                <div class="data-row row">
                    <div class="row-check sortable-handle col">
                        <input type="checkbox" class="grid-row-check">
                    </div>
                    <div class="row-index sortable-handle col"><span>No.</span></div>
                    ${columns.map(c => `<div class="col grid-static-col col-xs-${c.flex || 1 }">${esc(c.label)}</div>`).join('')}
                    <div class="col grid-static-col d-flex justify-content-center" style="cursor: pointer;">
                        <a><svg class="icon  icon-sm" style="filter: opacity(0.5)">
                            <use class="" href="#icon-setting-gear"></use>
                        </svg></a>
                    </div>
                </div>
            </div>
        </div>`;

    const body = `
        <div class="grid-body">
            <div class="rows">
                ${rows.map((r, i) => `
                <div class="grid-row" data-name="">
                    <div class="data-row row">
                        <div class="row-check col">
                            <input type="checkbox" class="grid-row-check">
                        </div>
                        <div class="row-index col">
                            <span>${i + 1}</span>
                        </div>
                        <div class="col grid-static-col col-xs-${columns[0].flex} bold">${esc(r.price_list)}</div>
                        <div class="col grid-static-col col-xs-${columns[1].flex} bold">${esc(r.margin)}%</div>
                        <div class="col grid-static-col col-xs-${columns[2].flex}">${esc(r.base_price_list)}</div>
                        <div class="col grid-static-col text-center" style="width: 90px;">
                            <button class="btn btn-default btn-xs grid-edit-row"
                                data-price_list="${esc(r.price_list)}"
                                data-margin="${esc(r.margin)}"
                                data-base_price_list="${esc(r.base_price_list)}">
                                <svg class="icon icon-sm" style="vertical-align: middle;">
                                    <use href="#icon-edit"></use>
                                </svg>
                                <span>${__('Edit')}</span>
                            </button>
                        </div>
                    </div>
                </div>
                `).join('')}
            </div>
        </div>`;

    const to_return = `
        ${toolbar}
        <div class="grid-field">
            <label class="control-label">Rule Prices</label>
            <div class="form-grid-container">
                <div class="form-grid">
                    ${header}${body}
                </div>
            </div>
            <div class="small form-clickable-section grid-footer">
                <div class="flex justify-between">
                    <div class="grid-buttons">
                        <button class="btn btn-xs btn-danger grid-remove-rows" data-action="delete_rows">
                            ${__('Delete')}
                        </button>
                        <button class="btn btn-xs btn-secondary grid-add-row">
                            ${__('Add Row')}
                        </button>
                    </div>
                </div>
            </div>
        </div>`;

    return to_return
}

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

        const html_field = frm.get_field('custom_rule_prices_html');
        if (html_field) {
            html_field.$wrapper.html(make_item_rules_grid());
            frm.events.add_price_rule_btn(frm);
        }
    },

    change_location_button: function(frm, section) {
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
        wrapper.invoice_receipt = new impex.item_details.ItemDetails(wrapper, frm.doc.item_code);
        dialog.show()
    },

    add_price_rule_btn: function(frm) {
        const html_field = frm.get_field('custom_rule_prices_html');
        if (html_field) {
            html_field.$wrapper.html(make_item_rules_grid());

            const $gridWrapper = html_field.$wrapper;
            const $select = $gridWrapper.find('select.custom-rule-select');
            const $rows = $gridWrapper.find('.grid-body .rows');
            const def_company = frappe.defaults.get_user_default('Company') || frappe.boot.sysdefaults.company;

            // Hide delete button initially
            const $deleteBtn = $gridWrapper.find('.grid-remove-rows');
            $deleteBtn.hide();

            // Render backend rows and include Edit button with data-attrs
            const render_grid_rows = (rows) => {
                const esc = (v) => frappe.utils.escape_html(String(v ?? ''));
                const html = (rows || []).map((r, i) => `
                    <div class="grid-row" data-name="${esc(r.name || '')}">
                        <div class="data-row row">
                            <div class="row-check col">
                                <input type="checkbox" class="grid-row-check">
                            </div>
                            <div class="row-index col">
                                <span>${i + 1}</span>
                            </div>
                            <div class="col grid-static-col col-xs-4 bold">${esc(r.price_list)}</div>
                            <div class="col grid-static-col col-xs-2 bold">${esc(r.margin)}%</div>
                            <div class="col grid-static-col col-xs-4">${esc(r.base_price_list || '')}</div>
                            <div class="col" style="width: 90px;">
                                <div class="btn-open-row grid-edit-row"
                                    data-price_list="${esc(r.price_list)}"
                                    data-margin="${esc(r.margin)}"
                                    data-base_price_list="${esc(r.base_price_list || '')}">
                                    <svg class="icon icon-sm" style="vertical-align: middle;">
                                        <use href="#icon-edit"></use>
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('');
                $rows.empty().append(html || '');
                update_delete_visibility();
            };

            // helper: show/hide delete button based on selection
            const update_delete_visibility = () => {
                const anySelected = $rows.find('.grid-row-check:checked').length > 0;
                if (anySelected) $deleteBtn.show(); else $deleteBtn.hide();
            };

            // helper: load rows from backend filtered by for_company
            const load_rule_rows = async () => {
                const company_filter = $select.val() || '';
                const r = await frappe.call({
                    method: 'impex.impex.doctype.price_change.price_change.get_item_rule_prices',
                    args: {
                        item_code: frm.doc.item_code,
                        for_company: company_filter
                    },
                    freeze: false
                });
                render_grid_rows(r.message || []);
            };

            // React to checkbox changes to toggle delete button
            $gridWrapper.off('change.rowcheck').on('change.rowcheck', '.grid-row-check', update_delete_visibility);

            // Handle delete click
            $gridWrapper.off('click.remove_rules').on('click.remove_rules', '.grid-remove-rows', async function () {
                const selected_names = $rows.find('.grid-row-check:checked')
                    .map((i, el) => $(el).closest('.grid-row').data('name'))
                    .get()
                    .filter(Boolean);

                if (!selected_names.length) return;

                frappe.confirm(
                    __('Delete {0} selected rule(s)?', [selected_names.length]),
                    async () => {
                        try {
                            await frappe.call({
                                method: 'impex.impex.doctype.price_change.price_change.delete_item_rule_prices',
                                args: {
                                    item_code: frm.doc.item_code,
                                    names: selected_names
                                },
                                freeze: true,
                                freeze_message: __('Deleting...')
                            });
                            await load_rule_rows();
                            frappe.show_alert({ message: __('Deleted'), indicator: 'green' });
                        } catch (e) {
                            frappe.msgprint({ message: __('Failed to delete rules'), indicator: 'red' });
                            throw e;
                        }
                    }
                );
            });

            frappe.db.get_list('Company', {fields: ['name'], limit: 0 }).then(async r => {
                $select.empty().append(
                    r.map(c => `<option value="${frappe.utils.escape_html(c.name)}">${frappe.utils.escape_html(c.name)}</option>`).join('')
                );
                if (def_company) $select.val(def_company);
                await load_rule_rows();
            });

            $gridWrapper.off('change.rule_filter').on('change.rule_filter', 'select.custom-rule-select', () => {
                load_rule_rows();
            });

            // Add Row -> open dialog, save to backend, then reload rows
            $gridWrapper.off('click.add_rule').on('click.add_rule', '.grid-add-row', function () {
                const current_company = $select.val() || def_company || '';
                const d = new frappe.ui.Dialog({
                    title: __('Add Rule Price'),
                    fields: [
                        { label: __('Price List'), fieldname: 'price_list', fieldtype: 'Link', options: 'Price List', reqd: 1 },
                        { label: __('Margin'), fieldname: 'margin', fieldtype: 'Float', reqd: 1, description: __('%') },
                        { label: __('Base Price List'), fieldname: 'base_price_list', fieldtype: 'Link', options: 'Price List' },
                        { label: __('For Company'), fieldname: 'for_company', fieldtype: 'Link', options: 'Company',
                            default: current_company || frappe.boot.sysdefaults.company },
                    ],
                    primary_action_label: __('Save'),
                    primary_action: async (values) => {
                        try {
                            await frappe.call({
                                method: 'impex.impex.doctype.price_change.price_change.add_item_rule_price',
                                args: {
                                    item_code: frm.doc.item_code,
                                    price_list: values.price_list,
                                    margin: values.margin,
                                    base_price_list: values.base_price_list || '',
                                    for_company: values.for_company || ''
                                },
                                freeze: true,
                                freeze_message: __('Saving rule...')
                            });

                            await load_rule_rows(); // refresh from backend with current filter
                            frappe.show_alert({ message: __('Rule added'), indicator: 'green' });
                            d.hide();
                        } catch (e) {
                            frappe.msgprint({ message: __('Failed to save rule'), indicator: 'red' });
                            throw e;
                        }
                    }
                });
                d.show();
            });

            // Optional: handle Edit click (opens dialog pre-filled, reuses add API to upsert)
            $gridWrapper.off('click.edit_rule').on('click.edit_rule', '.grid-edit-row', function () {
                const $btn = $(this);
                const d = new frappe.ui.Dialog({
                    title: __('Edit Rule Price'),
                    fields: [
                        { label: __('Price List'), fieldname: 'price_list', fieldtype: 'Link', options: 'Price List', reqd: 1,
                          default: $btn.data('price_list') },
                        { label: __('Margin'), fieldname: 'margin', fieldtype: 'Float', reqd: 1,
                          default: parseFloat($btn.data('margin')) || 0 },
                        { label: __('Base Price List'), fieldname: 'base_price_list', fieldtype: 'Link', options: 'Price List',
                          default: $btn.data('base_price_list') || '' },
                        { label: __('For Company'), fieldname: 'for_company', fieldtype: 'Link', options: 'Company',
                          default: $select.val() || def_company || '' },
                    ],
                    primary_action_label: __('Save'),
                    primary_action: async (values) => {
                        try {
                            await frappe.call({
                                method: 'impex.impex.doctype.price_change.price_change.add_item_rule_price',
                                args: {
                                    item_code: frm.doc.item_code,
                                    price_list: values.price_list,
                                    margin: values.margin,
                                    base_price_list: values.base_price_list || '',
                                    for_company: values.for_company || ''
                                },
                                freeze: true,
                                freeze_message: __('Saving rule...')
                            });
                            // reload current filtered rows
                            const r = await frappe.call({
                                method: 'impex.impex.doctype.price_change.price_change.get_item_rule_prices',
                                args: { item_code: frm.doc.item_code, for_company: $select.val() || '' }
                            });
                            render_grid_rows(r.message || []);
                            d.hide();
                            frappe.show_alert({ message: __('Rule updated'), indicator: 'green' });
                        } catch (e) {
                            frappe.msgprint({ message: __('Failed to update rule'), indicator: 'red' });
                            throw e;
                        }
                    }
                });
                d.show();
            });
        }
    }
});