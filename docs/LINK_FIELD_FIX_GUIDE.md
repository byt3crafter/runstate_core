# Link Field Dropdown Fix Guide

## Problem

Link fields (like Warehouse, Item, Customer, etc.) not showing dropdown options when clicked or typed into. Browser console shows:

```
TypeError: can't access property "reduce", results is undefined
    merge_duplicates link.js:446
    callback link.js:298
```

## Root Cause

The impex app overrides `frappe.desk.search.search_link` in `hooks.py`:

```python
override_whitelisted_methods = {
    "frappe.desk.search.search_link": "impex.extends.search.search_link",
}
```

The custom `search.py` was returning data using `frappe.response["results"]` but frappe.call expects `frappe.response["message"]`.

## Files Affected

1. `impex/extends/search.py`
2. `impex/public/js/link.js`

## Fix

### 1. Fix search.py (Backend)

**File:** `impex/extends/search.py`

**Change line ~54 from:**
```python
frappe.response["results"] = build_for_autosuggest(
    frappe.response["values"], doctype=doctype
)
```

**To:**
```python
frappe.response["message"] = build_for_autosuggest(
    frappe.response["values"], doctype=doctype
)
```

### 2. Fix link.js (Frontend)

**File:** `impex/public/js/link.js`

**In the callback function (~line 104), change all occurrences of:**
- `r.results` → `r.message`
- `r.results.push` → `r.message.push`
- `r.results.concat` → `r.message.concat`

**Also add null check:**
```javascript
// Change from:
r.results = me.merge_duplicates(r.results);

// To:
r.message = me.merge_duplicates(r.message || []);
```

**Add link title caching (after `me.toggle_href(doctype);`):**
```javascript
r.message.forEach((item) => {
    frappe.utils.add_link_title(doctype, item.value, item.label);
});
```

## After Fix

1. **For Python changes:** Restart frappe web server
   ```bash
   bench restart
   # or for docker:
   docker restart <frappe_container>
   ```

2. **For JS changes:** Rebuild assets
   ```bash
   bench build --app impex
   ```

3. Hard refresh browser (Ctrl+Shift+R)

## Why This Happens

- Frappe's `frappe.call()` method expects the API response in `frappe.response["message"]`
- The JavaScript callback receives this as `r.message`
- When the backend returns data in `frappe.response["results"]`, the JS receives `r.message` as `undefined`
- Calling `.reduce()` on `undefined` throws the TypeError

## Commit Reference

```
fix: Fix link field dropdown TypeError and search response format

- Changed frappe.response["results"] to frappe.response["message"] in search.py
  to match frappe.call expected response format
- Updated link.js to use r.message instead of r.results
- Added null check (r.message || []) to prevent "reduce" error on undefined
- Added frappe.utils.add_link_title() call for proper link title caching
```
