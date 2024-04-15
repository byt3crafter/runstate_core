from impex.extends.price_lsit import update_supplier_price_list


def on_submit(doc, method):
    update_supplier_price_list(doc, method)
