// Common reusable Rule Prices grid (Item, Item Group, Supplier)
frappe.provide('impex.rule_prices');

(function() {
    const esc = (v) => frappe.utils.escape_html(String(v ?? ''));

    function grid_template() {
        return `
            <div class="grid-field">
                <div class="frappe-control input-max-width" style="margin-bottom:8px;">
                    <label class="control-label">${__('For Company')}</label>
                    <div class="control-input-wrapper">
                        <div class="control-input">
                            <select class="form-control input-sm rp-company-filter"></select>
                        </div>
                    </div>
                </div>
                <label class="control-label">${__('Rule Prices')}</label>
                <div class="form-grid-container">
                    <div class="form-grid">
                        <div class="grid-heading-row">
                            <div class="grid-row">
                                <div class="data-row row">
                                    <div class="row-check sortable-handle col">
                                        <input type="checkbox" class="grid-row-check-all">
                                    </div>
                                    <div class="row-index sortable-handle col"><span>No.</span></div>
                                    <div class="col grid-static-col col-xs-4">${__('Price List')}</div>
                                    <div class="col grid-static-col col-xs-2">${__('Margin')}</div>
                                    <div class="col grid-static-col col-xs-4">${__('Base on Price List')}</div>
                                    <div class="col grid-static-col text-center" style="width:90px;">
                                           <svg class="icon  icon-sm" style="filter: opacity(0.5)">
                                           <use class="" href="#icon-setting-gear"></use>
                         </svg>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="grid-body">
                            <div class="rows"></div>
                        </div>
                    </div>
					<div class="small form-clickable-section grid-footer">
                            <div class="flex justify-between">
                                <div class="grid-buttons">
                                    <button class="btn btn-xs btn-danger rp-delete" style="display:none;">
                                        ${__('Delete')}
                                    </button>
                                    <button class="btn btn-xs btn-secondary rp-add">
                                        ${__('Add Row')}
                                    </button>
                                </div>
                            </div>
                        </div>
                </div>
            </div>`;
    }

    async function load_companies($select, def_company) {
        const r = await frappe.db.get_list('Company', { fields: ['name'], limit: 0 });
        $select.empty().append(
            r.map(c => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('')
        );
        if (def_company) $select.val(def_company);
    }

    impex.rule_prices.setup = function(frm, opts = {}) {
        const html_fieldname = opts.html_field || 'custom_rule_prices_html';
        const html_field = frm.get_field(html_fieldname);
        if (!html_field) return;

        // Guard: prevent duplicate wiring. If already initialized for this doc + same doctype, just refresh rows.
        if (html_field.$wrapper.data('rp-initialized') && html_field.$wrapper.data('rp-docname') === frm.doc.name) {
            html_field.$wrapper.find('.rp-company-filter').trigger('change');
            return;
        }

        html_field.$wrapper
            .data('rp-initialized', true)
            .data('rp-docname', frm.doc.name);

        // Render skeleton fresh (clears old handlers)
        html_field.$wrapper.html(grid_template());

        const $wrap = html_field.$wrapper;
        const $rows = $wrap.find('.rows');
        const $deleteBtn = $wrap.find('.rp-delete');
        const $companySelect = $wrap.find('.rp-company-filter');
        const def_company = frappe.defaults.get_user_default('Company') || frappe.boot.sysdefaults.company;

        const update_delete_visibility = () => {
            const anySelected = $rows.find('.rp-row-check:checked').length > 0;
            $deleteBtn.toggle(anySelected);
        };

        const render_rows = (rows) => {
            const html = (rows || []).map((r, i) => `
                <div class="grid-row" data-name="${esc(r.name || '')}">
                    <div class="data-row row">
                        <div class="row-check col">
                            <input type="checkbox" class="grid-row-check rp-row-check">
                        </div>
                        <div class="row-index col"><span>${i + 1}</span></div>
                        <div class="col grid-static-col col-xs-4 bold">${esc(r.price_list)}</div>
                        <div class="col grid-static-col col-xs-2 bold">${esc(r.margin)}%</div>
                        <div class="col grid-static-col col-xs-4">${esc(r.base_price_list || '')}</div>
                        <div class="col" style="width:90px;">
                            <div class="btn-open-row rp-edit"
                                data-name="${esc(r.name)}"
                                data-price_list="${esc(r.price_list)}"
                                data-margin="${esc(r.margin)}"
                                data-base_price_list="${esc(r.base_price_list || '')}">
                                <svg class="icon icon-sm" style="vertical-align:middle;">
                                    <use href="#icon-edit"></use>
                                </svg>
                            </div>
                        </div>
                    </div>
                </div>`).join('');
            $rows.empty().append(html);
            update_delete_visibility();
        };

        const load_rows = async () => {
            const r = await frappe.call({
                method: 'impex.impex.doctype.price_change.price_change.get_rule_prices',
                args: {
                    doctype: frm.doctype,
                    docname: frm.doc.name,
                    for_company: $companySelect.val() || ''
                },
                freeze: false
            });
            render_rows(r.message || []);
        };

        // Remove any previous namespaced handlers before binding (idempotent)
        $wrap.off('.rp');

        $wrap
            .on('change.rp', '.rp-row-check', update_delete_visibility)
            .on('change.rp', '.rp-company-filter', load_rows)
            .on('click.rp', '.rp-edit', function() {
                const $b = $(this);
                const d = new frappe.ui.Dialog({
                    title: __('Edit Rule Price'),
                    fields: [
                        { fieldname: 'price_list', label: __('Price List'), fieldtype: 'Link', options: 'Price List', reqd: 1, default: $b.data('price_list') },
                        { fieldname: 'margin', label: __('Margin'), fieldtype: 'Float', reqd: 1, default: parseFloat($b.data('margin')) || 0, description: '%' },
                        { fieldname: 'base_price_list', label: __('Base Price List'), fieldtype: 'Link', options: 'Price List', default: $b.data('base_price_list') || '' },
                        { fieldname: 'for_company', label: __('For Company'), fieldtype: 'Link', options: 'Company', reqd: 1, default: $companySelect.val() || def_company || '' },
                    ],
                    primary_action_label: __('Save'),
                    primary_action: async (values) => {
                        await frappe.call({
                            method: 'impex.impex.doctype.price_change.price_change.add_rule_price',
                            args: {
                                doctype: frm.doctype,
                                docname: frm.doc.name,
                                price_list: values.price_list,
                                margin: values.margin,
                                base_price_list: values.base_price_list || '',
                                for_company: values.for_company
                            },
                            freeze: true
                        });
                        await load_rows();
                        d.hide();
                        frappe.show_alert({ message: __('Updated'), indicator: 'green' });
                    }
                });
                d.show();
            })
            .on('click.rp', '.rp-add', function() {
                const current_company = $companySelect.val() || def_company || '';
                const d = new frappe.ui.Dialog({
                    title: __('Add Rule Price'),
                    fields: [
                        { fieldname: 'price_list', label: __('Price List'), fieldtype: 'Link', options: 'Price List', reqd: 1 },
                        { fieldname: 'margin', label: __('Margin'), fieldtype: 'Float', reqd: 1, description: '%' },
                        { fieldname: 'base_price_list', label: __('Base Price List'), fieldtype: 'Link', options: 'Price List' },
                        { fieldname: 'for_company', label: __('For Company'), fieldtype: 'Link', options: 'Company', default: current_company },
                    ],
                    primary_action_label: __('Save'),
                    primary_action: async (values) => {
                        await frappe.call({
                            method: 'impex.impex.doctype.price_change.price_change.add_rule_price',
                            args: {
                                doctype: frm.doctype,
                                docname: frm.doc.name,
                                price_list: values.price_list,
                                margin: values.margin,
                                base_price_list: values.base_price_list || '',
                                for_company: values.for_company || current_company
                            },
                            freeze: true
                        });
                        await load_rows();
                        d.hide();
                        frappe.show_alert({ message: __('Added'), indicator: 'green' });
                    }
                });
                d.set_value('for_company', current_company);
                d.show();
            })
            .on('click.rp', '.rp-delete', async function() {
                const names = $rows.find('.rp-row-check:checked')
                    .map((i, el) => $(el).closest('.grid-row').data('name'))
                    .get()
                    .filter(Boolean);
                if (!names.length) return;
                frappe.confirm(
                    __('Delete {0} selected rule(s)?', [names.length]),
                    async () => {
                        await frappe.call({
                            method: 'impex.impex.doctype.price_change.price_change.delete_rule_prices',
                            args: { doctype: frm.doctype, docname: frm.doc.name, names },
                            freeze: true
                        });
                        await load_rows();
                        frappe.show_alert({ message: __('Deleted'), indicator: 'green' });
                    }
                );
            });

        (async () => {
            await load_companies($companySelect, def_company);
            await load_rows();
        })();
    };

})();