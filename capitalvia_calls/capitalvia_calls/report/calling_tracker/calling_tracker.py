# Copyright (c) 2013, Vikram and contributors
# For license information, please see license.txt

# import frappe


from __future__ import unicode_literals
import frappe
import json
from datetime import date, timedelta
from datetime import datetime
import hashlib
import datetime
from frappe.utils import getdate, flt, cint
from frappe import _

date_list = []
date_set = set()

def execute(filters=None):
    data = get_data(filters)
    columns = get_columns(filters)
    return columns, data

def get_data(filters):
    if filters.get("report_option"):
        toDate = date.today()
        report_option = filters.get("report_option")

        if report_option == "Last 30 days":
            fromDate = toDate - timedelta(days=30)
        elif report_option == "Last 15 days":
            fromDate = toDate - timedelta(days=15)
        elif report_option == "Last 7 days":
            fromDate = toDate - timedelta(days=7)


        if(filters.get("call_status") == "Answered"):
            whereCondition = 'and call_status = "ANSWERED"'
        elif(filters.get("call_status") == "No Answer"):
            whereCondition = 'and call_status = "No ANSWER"'
        elif(filters.get("call_status") == "Failed"):
            whereCondition = 'and call_status = "FAILED"'
        elif(filters.get("call_status") == "Busy"):
            whereCondition = 'and call_status = "BUSY"'
        elif(filters.get("call_status") == "All"):
            whereCondition = ' '

        callLogsData = frappe.db.sql("""SELECT date_format(`tabCall Logs`.call_time,"%d-%m-%Y"),`tabCall Logs`.sales_person as `Employee Name`,`tabSales Person`.parent_sales_person AS parent_sales_person_name,`tabCall Logs`.extension as `User Extension`,count(*) as total_attempts,SEC_TO_TIME(SUM(TIME_TO_SEC(billing_second))) from `tabCall Logs` INNER JOIN `tabSales Person` ON `tabCall Logs`.sales_person = `tabSales Person`.sales_person_name  where date_format(call_time,"%Y-%m-%d")  between '{0}'  AND '{1}' {2} AND `tabCall Logs`.call_type!="Internal" group by date(call_time),sales_person order by date(call_time) DESC """.format(fromDate, toDate, whereCondition))

        salesPersonSet = set()
        salesPersonWiseData = {}
        result = []

        # Calculate yesterday's date
        yesterday = (toDate - timedelta(days=1)).strftime("%d-%m-%Y")

        for data in callLogsData:
            if data[1]:
                Cdate = data[0]
                salesPerson = data[1]
                parentSalesPerson = data[2]
                extension = data[3]
                attempts = data[4]
                time = data[5]

                if salesPerson not in salesPersonSet:
                    salesPersonSet.add(salesPerson)
                    salesPersonWiseData[salesPerson] = {
                        "parent_sales_person": parentSalesPerson,
                        "user_extension": extension,
                        "total_attempts": attempts,
                        Cdate: time
                    }
                else:
                    salesPersonWiseData[salesPerson][Cdate] = time
                    salesPersonWiseData[salesPerson]["total_attempts"] += attempts

                if str(Cdate) not in date_set:
                    date_set.add(str(Cdate))
                    date_list.append(Cdate)

        # Sort the dates in descending order
        date_list.sort(key=lambda date: datetime.datetime.strptime(date, "%d-%m-%Y"), reverse=True)

        # Add yesterday's total attempts
        for salesperson in salesPersonWiseData:
            # Initialize yesterday's attempts as 0 if no attempts were recorded for yesterday
            salesPersonWiseData[salesperson]["yesterday_attempts"] = 0

            # Check if data exists for yesterday and update with total attempts
            for data in callLogsData:
                if data[1] == salesperson and data[0] == yesterday:
                    salesPersonWiseData[salesperson]["yesterday_attempts"] += data[4]  # Add the total attempts for yesterday

        # Prepare the result with all the necessary fields
        for key, value in salesPersonWiseData.items():
            data_row = {"sales_person": key}
            for key1, value1 in value.items():
                data_row[key1] = value1
            result.append(data_row)

        return result

def get_columns(filters=None):
    columns = [
        {"label": _("Sales Person"), "fieldname": "sales_person", "fieldtype": "Data", "width": 80},
        {"label": _("Sales Manager"), "fieldname": "parent_sales_person", "fieldtype": "Data", "width": 70},
        {"label": _("User Extension"), "fieldname": "user_extension", "fieldtype": "Data", "width": 70},
        {"label": _("Total Attempts"), "fieldname": "total_attempts", "fieldtype": "Data", "width": 70},
        {"label": _("Last Day Attempts"), "fieldname": "yesterday_attempts", "fieldtype": "Data", "width": 80}  # New column for yesterday's attempts
    ]

    for data in date_list:
        columns.append({"label": _(data), "fieldname": data, "fieldtype": "Data", "width": 75})

    return columns

