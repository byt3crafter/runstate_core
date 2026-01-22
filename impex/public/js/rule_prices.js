// Common reusable Rule Prices grid (Item, Item Group, Supplier)
frappe.provide('impex.rule_prices');

(function() {
    const esc = (v) => frappe.utils.escape_html(String(v ?? ''));

    // Accept is_supplier to render extra columns and adjust widths
    function grid_template(is_supplier) {
        // Column classes for Supplier vs others
        const supplierCols = is_supplier ? `
            <div class="col grid-static-col col-xs-2">${__('Item Code')}</div>
            <div class="col grid-static-col col-xs-3">${__('Item Name')}</div>
        ` : '';

        const priceListColClass = is_supplier ? 'col-xs-2' : 'col-xs-3';
        const marginColClass    = is_supplier ? 'col-xs-1' : 'col-xs-2';
        const baseColClass      = is_supplier ? 'col-xs-2' : 'col-xs-4';
        const actionsHeader     = `<div class="col grid-static-col text-center" style="width:90px;">
                    <svg class="icon  icon-sm" style="filter: opacity(0.5)">
                        <use class="" href="#icon-setting-gear"></use>
                    </svg>
               </div>`;

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
                                    ${supplierCols}
                                    <div class="col grid-static-col ${priceListColClass}">${__('Price List')}</div>
                                    <div class="col grid-static-col ${marginColClass}">${__('Margin')}</div>
                                    <div class="col grid-static-col ${baseColClass}">${__('Base on Price List')}</div>
                                    ${actionsHeader}
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
                            <!-- Pager (hidden until > 50 rows) -->
                            <div class="rp-pager" style="display:none; gap:8px; align-items:center;">
                                <button class="btn btn-xs btn-default rp-prev" disabled>${__('Prev')}</button>
                                <span class="rp-page-info">Page 1 of 1 (0)</span>
                                <button class="btn btn-xs btn-default rp-next" disabled>${__('Next')}</button>
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

        const is_supplier = frm.doctype === 'Supplier';

        // Prevent duplicate wiring for the same doc
        if (html_field.$wrapper.data('rp-initialized') && html_field.$wrapper.data('rp-docname') === frm.doc.name) {
            html_field.$wrapper.find('.rp-company-filter').trigger('change');
            return;
        }
        html_field.$wrapper.data('rp-initialized', true).data('rp-docname', frm.doc.name);

        // Fresh skeleton
        html_field.$wrapper.html(grid_template(is_supplier));

        const $wrap = html_field.$wrapper;
        const $rows = $wrap.find('.rows');
        const $deleteBtn = $wrap.find('.rp-delete');
        const $companySelect = $wrap.find('.rp-company-filter');
        const def_company = frappe.defaults.get_user_default('Company') || frappe.boot.sysdefaults.company;

        // Pager elements and state
        const $pager = $wrap.find('.rp-pager');
        const $prev = $wrap.find('.rp-prev');
        const $next = $wrap.find('.rp-next');
        const $pageInfo = $wrap.find('.rp-page-info');
        let allRows = [];
        let page = 1;
        const pageSize = 50;

        const update_delete_visibility = () => {
            const anySelected = $rows.find('.rp-row-check:checked').length > 0;
            $deleteBtn.toggle(anySelected);
        };

        const render_rows = (rows) => {
            // Body column classes aligned with header classes
            const priceListColClass = is_supplier ? 'col-xs-2' : 'col-xs-3';
            const marginColClass    = is_supplier ? 'col-xs-1' : 'col-xs-2';
            const baseColClass      = is_supplier ? 'col-xs-2' : 'col-xs-4';
            const actionsColClass   = 'col text-center';

            const html = (rows || []).map((r, i) => `
                <div class="grid-row" data-name="${esc(r.name || '')}">
                    <div class="data-row row">
                        <div class="row-check col">
                            <input type="checkbox" class="grid-row-check rp-row-check">
                        </div>
                        <div class="row-index col"><span>${i + 1 + (page - 1) * pageSize}</span></div>
                        ${is_supplier ? `
                        <div class="col grid-static-col col-xs-2">${esc(r.item_code || '')}</div>
                        <div class="col grid-static-col col-xs-3">
                            <span
                                class="rp-item-name"
                                title="${esc(r.item_name || '')}"
                                style="display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
                                ${esc(r.item_name || '')}
                            </span>
                        </div>
                        ` : ''}
                        <div class="col grid-static-col ${priceListColClass} bold">${esc(r.price_list)}</div>
                        <div class="col grid-static-col ${marginColClass} bold">${esc(r.margin)}%</div>
                        <div class="col grid-static-col ${baseColClass}">${esc(r.base_price_list || '')}</div>
                        <div class="${actionsColClass}">
                            <div class="btn-open-row rp-edit"
                                data-name="${esc(r.name)}"
                                data-item_code="${esc(r.item_code || '')}"
                                data-item_name="${esc(r.item_name || '')}"
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

        // Render current page and update pager UI
        const render_paged_rows = () => {
            const total = allRows.length;
            const totalPages = Math.max(1, Math.ceil(total / pageSize));
            if (page > totalPages) page = totalPages;
            if (page < 1) page = 1;

            const start = (page - 1) * pageSize;
            const subset = allRows.slice(start, start + pageSize);
            render_rows(subset);

            if (total > pageSize) {
                $pager.show();
            } else {
                $pager.hide();
            }
            $pageInfo.text(`Page ${page} of ${totalPages} (${total})`);
            $prev.prop('disabled', page <= 1);
            $next.prop('disabled', page >= totalPages);
        };

        const load_rows = async () => {
            // Skip loading for unsaved documents
            if (frm.is_new()) {
                allRows = [];
                page = 1;
                render_paged_rows();
                return;
            }
            const r = await frappe.call({
                method: 'impex.impex.doctype.price_change.price_change.get_rule_prices',
                args: {
                    doctype: frm.doctype,
                    docname: frm.doc.name,
                    for_company: $companySelect.val() || ''
                },
                freeze: false
            });
            allRows = r.message || [];
            page = 1;
            render_paged_rows();
        };

        // Clear old handlers and bind new ones (namespaced)
        $wrap.off('.rp');

        $wrap
            .on('change.rp', '.rp-row-check', update_delete_visibility)
            .on('change.rp', '.rp-company-filter', load_rows)
            .on('click.rp', '.rp-prev', () => { page -= 1; render_paged_rows(); })
            .on('click.rp', '.rp-next', () => { page += 1; render_paged_rows(); })
            .on('click.rp', '.rp-edit', function() {
                const $b = $(this);
                const fields = [
                    ...(is_supplier ? [
                        { fieldname: 'item_code', label: __('Item Code'), fieldtype: 'Link', options: 'Item', reqd: 1, default: $b.data('item_code') },
                        { fieldname: 'item_name', label: __('Item Name'), fieldtype: 'Data', read_only: 1, default: $b.data('item_name') || '' },
                    ] : []),
                    { fieldname: 'price_list', label: __('Price List'), fieldtype: 'Link', options: 'Price List', reqd: 1, default: $b.data('price_list') },
                    { fieldname: 'margin', label: __('Margin'), fieldtype: 'Float', reqd: 1, default: parseFloat($b.data('margin')) || 0, description: '%' },
                    { fieldname: 'base_price_list', label: __('Base Price List'), fieldtype: 'Link', options: 'Price List', default: $b.data('base_price_list') || '' },
                    { fieldname: 'for_company', label: __('For Company'), fieldtype: 'Link', options: 'Company', reqd: 1, default: $companySelect.val() || def_company || '' },
                ];

                const d = new frappe.ui.Dialog({
                    title: __('Edit Rule Price'),
                    fields,
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
                                for_company: values.for_company,
                                item_code: is_supplier ? values.item_code : undefined,
                                item_name: is_supplier ? (values.item_name || '') : undefined,
                            },
                            freeze: true
                        });
                        await load_rows();
                        d.hide();
                        frappe.show_alert({ message: __('Updated'), indicator: 'green' });
                    }
                });

                if (is_supplier) {
                    d.$wrapper.on('change.rp', '[data-fieldname="item_code"]', async () => {
                        const code = d.get_value('item_code');
                        if (!code) return;
                        const r = await frappe.db.get_value('Item', code, 'item_name');
                        if (r && r.message && r.message.item_name) {
                            d.set_value('item_name', r.message.item_name);
                        }
                    });
                }

                d.show();
            })
            .on('click.rp', '.rp-add', function() {
                const current_company = $companySelect.val() || def_company || '';
                const fields = [
                    ...(is_supplier ? [
                        { fieldname: 'item_code', label: __('Item Code'), fieldtype: 'Link', options: 'Item', reqd: 1 },
                        { fieldname: 'item_name', label: __('Item Name'), fieldtype: 'Data', read_only: 1 },
                    ] : []),
                    { fieldname: 'price_list', label: __('Price List'), fieldtype: 'Link', options: 'Price List', reqd: 1 },
                    { fieldname: 'margin', label: __('Margin'), fieldtype: 'Float', reqd: 1, description: '%' },
                    { fieldname: 'base_price_list', label: __('Base Price List'), fieldtype: 'Link', options: 'Price List' },
                    { fieldname: 'for_company', label: __('For Company'), fieldtype: 'Link', options: 'Company', default: current_company },
                ];

                const d = new frappe.ui.Dialog({
                    title: __('Add Rule Price'),
                    fields,
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
                                for_company: values.for_company || current_company,
                                item_code: is_supplier ? values.item_code : undefined,
                                item_name: is_supplier ? (values.item_name || '') : undefined,
                            },
                            freeze: true
                        });
                        await load_rows();
                        d.hide();
                        frappe.show_alert({ message: __('Added'), indicator: 'green' });
                    }
                });

                if (is_supplier) {
                    d.$wrapper.on('change.rp', '[data-fieldname="item_code"]', async () => {
                        const code = d.get_value('item_code');
                        if (!code) return;
                        const r = await frappe.db.get_value('Item', code, 'item_name');
                        if (r && r.message && r.message.item_name) {
                            d.set_value('item_name', r.message.item_name);
                        }
                    });
                }

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