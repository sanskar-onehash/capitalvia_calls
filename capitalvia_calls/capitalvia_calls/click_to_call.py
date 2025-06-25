import frappe
import requests

from capitalvia_calls.capitalvia_calls.tlsv1adapter import TLSv1Adapter


@frappe.whitelist()
def click_to_call(target):
    employee = frappe.get_cached_doc("Employee", {"user_id": frappe.session.user})
    sales_person = frappe.get_cached_doc("Sales Person", {"employee": employee.name})
    primary_extension = sales_person.custom_primary_extension
    if not primary_extension:
        frappe.throw("No Extension found to call.")
    try:
        serverInfo = frappe.get_cached_doc(
            "Calling Servers",
            {"enabled": 1, "click_to_call": 1},
        )
        header = {
            "Authorization": serverInfo.authorization_key,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"target": target, "extension": primary_extension}
        # Create a session and mount the custom adapter to enforce TLSv1
        session = requests.Session()
        session.mount("https://", TLSv1Adapter())

        url = f"{serverInfo.link_public_address}/click2call.php"

        session.post(url, headers=header, data=data, verify=False)
    except Exception as e:
        frappe.log_error("Click to call error", e)
