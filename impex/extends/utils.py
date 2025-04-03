import frappe
from frappe.utils import file_lock, now_datetime
import json
from frappe import _

def queue_action(self, action, **kwargs):
	#Run an action in background
	from frappe.utils.background_jobs import enqueue

	if file_lock.lock_exists(self.get_signature()):
		frappe.throw(_('This document is currently queued for execution. Please try again'),
			title=_('Document Queued'))
	
	frappe.db.set_value(self.doctype, self.name, 'queue_status', 'Queued',  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queue_failed', 0,  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queue_comment', '',  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queued_date', now_datetime(),  update_modified=False)
	frappe.db.set_value(self.doctype, self.name, 'queued_by', frappe.session.user,  update_modified=False)
	self.lock()
	enqueue('impex.extends.utils.execute_action', doctype=self.doctype, name=self.name,
		action=action, **kwargs)
	
def execute_action(doctype, name, action, **kwargs):
	"""Execute an action on a document (called by background worker)"""
	doc = frappe.get_doc(doctype, name)
	doc.unlock()
	try:
		getattr(doc, action)(**kwargs)
		frappe.db.set_value(doctype, name, "queue_status", "Completed", update_modified=False)
	except Exception:
		frappe.db.rollback()

		# add a comment (?)
		if frappe.local.message_log:
			msg = json.loads(frappe.local.message_log[-1]).get('message')
		else:
			msg = '<pre><code>' + frappe.get_traceback() + '</pre></code>'

		doc.add_comment('Comment', _('Action Failed') + '<br><br>' + msg)
		frappe.db.set_value(doctype, name, 'queue_failed', 1, update_modified=False)
		frappe.db.set_value(doctype, name, 'queue_status', "Failed", update_modified=False)
		frappe.db.set_value(doctype, name, 'queue_comment', msg, update_modified=False)
		doc.notify_update()