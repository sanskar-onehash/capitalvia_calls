import frappe
import json
import requests
import pprint
from datetime import datetime, timedelta

# new
import ssl
from requests.adapters import HTTPAdapter


# Creating custom context which enforces TLS v1 and weak cipher bypass
class TLSv1Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        context.set_ciphers("DEFAULT@SECLEVEL=0")
        kwargs["ssl_context"] = context
        return super().init_poolmanager(*args, **kwargs)


@frappe.whitelist()
def create_automatic_call_logs():
    pp = pprint.PrettyPrinter(indent=4)
    limit_page_length = 4000
    extension_wise_sales_person = {}
    calling_servers = frappe.get_list(
        "Calling Servers",
        fields=["*"],
        filters=[["Calling Servers", "enabled", "=", 1]],
        limit_page_length=20,
    )

    def logger(message, mode="Info"):
        nowtime = datetime.now()
        formattedTime = nowtime.strftime("%Y-%m-%d %H:%M:%S.%f")
        finalMessage = "[" + formattedTime + "] [" + mode + "] " + message
        # frappe.log_error(finalMessage)

    def convert_to_time(parms):
        return str(timedelta(seconds=parms))

    def insert_many(docs):
        if len(docs):
            doctype = docs[0]["doctype"]
            fields = [key for key in docs[0]]
            values = []
            for doc in docs:
                doc_values = []
                for field in fields:
                    doc_values.append(doc[field])
            frappe.db.bulk_insert(doctype, fields, values)
            frappe.db.commit()

    def retrieve_cdr(server_info):
        header = {
            "Authorization": server_info["authorization_key"],
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "custom": " AND id>"
            + str(server_info["last_insert_id"])
            + " ORDER BY id ASC ",
            "limit": server_info["limit"],
        }

        # Create a session and mount the custom adapter to enforce TLSv1
        session = requests.Session()
        session.mount("https://", TLSv1Adapter())

        url = f"{server_info['link_public_address']}/api/api.php?cmd=cdrreport&custom={data['custom']}&limit={data['limit']}"

        response = session.post(url, headers=header, data=data, verify=False)
        return json.loads(response.text, strict=False)

    def determine_call_type(cdr_log):
        src = cdr_log["src"]
        dst = cdr_log["dst"]
        callType = ""
        if len(cdr_log["src"]) == 4 and len(cdr_log["dst"]) == 4:
            callType = "Internal"
        elif len(cdr_log["src"]) == 4:
            callType = "Outgoing"
        elif len(cdr_log["dst"]) == 4:
            callType = "Incoming"
            src = cdr_log["dst"]
            dst = cdr_log["src"]
        elif len(cdr_log["src"]) == 10 and len(cdr_log["dst"]) == 10:
            if (src[-10:-4]) in ["731381", "731673"]:
                callType = "Outgoing"
                src = cdr_log["src"][-4:]
            elif (dst[-10:-4]) in ["731381", "731673"]:
                callType = "Incoming"
                src = cdr_log["dst"][-4:]
                dst = cdr_log["src"]
            else:
                callType = "Outgoing"
        return callType, src, dst

    def get_play_link(log, server):
        return (
            server["link_address"]
            + "/download.php?val=listen&file="
            + (log["recordingfile"]).lstrip(server["file_prefix"])
        )

    def init_cdr_log_insertion(cdr_logs, server):
        log_data = []
        i = 1
        excludeList = []
        if server["exclude_list"]:
            excludeList = server["exclude_list"].split(",")
        lastInsertedID = server["last_insert_id"]
        logger("[Start] Log Insertion Started.", "Call Logger")
        for log in cdr_logs:
            callType, src, dst = determine_call_type(log)
            if "id" in log:
                lastInsertedID = log["id"]
            else:
                lastInsertedID = 0

            if src in excludeList:
                continue
            if src in extension_wise_sales_person:
                salesPerson = extension_wise_sales_person[src]

                if "recordingfile" in log:
                    pass
                elif "userfield" in log:
                    log["recordingfile"] = log["userfield"]
                else:
                    logger(
                        "Call record not inserted Unique ID="
                        + server["link_address"]
                        + " "
                        + str(log["uniqueid"]),
                        "Error",
                    )
                    continue
                log_to_insert = {
                    "customer_phone": dst,
                    "extension": src,
                    "call_unique_id": log["uniqueid"],
                    "recording": log["recordingfile"],
                    #'call_duration' : log['duration'],
                    "calling_duration": convert_to_time(int(log["duration"])),
                    "billing_second": convert_to_time(int(log["billsec"])),
                    #'bill_second':log['billsec'],
                    "call_status": log["disposition"],
                    "doctype": "Call Logs",
                    "call_time": log["calldate"],
                    "calling_server": server["link_address"],
                    "sales_person": salesPerson.strip(),
                    "call_type": callType,
                    "play_recording": get_play_link(log, server),
                }
                log_data.append(log_to_insert)
                if i == 200:
                    insert_many(log_data)
                    update_last_insert_id(server, lastInsertedID)
                    logger("[End] 200 Records Inserted")
                    i = 0
                    log_data = []
                i = i + 1

        if len(log_data) > 0 and i < 200:
            insert_many(log_data)
            update_last_insert_id(server, lastInsertedID)
            logger("[End] " + str(len(log_data)) + " Records Inserted")
        elif len(log_data) == 0:
            update_last_insert_id(server, lastInsertedID)
            logger(
                "[End] "
                + str(len(log_data))
                + " Records Inserted Last Insert ID updated to "
                + str(lastInsertedID)
            )

    def update_last_insert_id(server, inserted_id):
        frappe.db.set_value(
            server["doctype"], server["name"], "last_insert_id", inserted_id
        )
        frappe.db.commit()

    def map_extension_wise_sales_person():
        enabled_sales_persons = frappe.get_all(
            "Sales Person",
            ["custom_primary_extension", "custom_secondary_extension", "name"],
            {"enabled": 1, "custom_primary_extension": ["is", "set"]},
        )
        for sales_person in enabled_sales_persons:
            if sales_person["custom_primary_extension"]:
                extension_wise_sales_person[
                    sales_person["custom_primary_extension"]
                ] = sales_person["name"]
            if sales_person["custom_secondary_extension"]:
                extension_wise_sales_person[
                    sales_person["custom_secondary_extension"]
                ] = sales_person["name"]

    map_extension_wise_sales_person()

    for server in calling_servers:
        logger(
            "[Start] Call Logs Fetched from Calling server " + server["link_address"],
            "Debug",
        )
        cdrLogs = retrieve_cdr(server)
        logger(
            "[End] Call Logs Fetched from Calling server "
            + server["link_address"]
            + " "
            + str(len(cdrLogs)),
            "Debug2",
        )
        init_cdr_log_insertion(cdrLogs, server)
