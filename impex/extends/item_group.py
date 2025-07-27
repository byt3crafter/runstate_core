import frappe
from erpnext.setup.doctype.item_group.item_group import ItemGroup
from impex.impex.doctype.price_change.price_change import add_auto_price_rules

class CustomItemGroup(ItemGroup):
	def on_update(self):
		super(CustomItemGroup, self).on_update()
		add_auto_price_rules("Item Group", self.name)