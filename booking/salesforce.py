import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


logger = logging.getLogger(__name__)


class SalesforceError(Exception):
    pass


class SalesforceClient:
    def __init__(self):
        self.client_id = settings.SALESFORCE_CLIENT_ID
        self.client_secret = settings.SALESFORCE_CLIENT_SECRET
        self.account_id = settings.SALESFORCE_ACCOUNT_ID
        self.login_url = settings.SALESFORCE_LOGIN_URL
        self.api_version = settings.SALESFORCE_API_VERSION
        self.access_token = ""
        self.instance_url = ""

    @property
    def configured(self):
        return bool(self.client_id and self.client_secret and self.account_id)

    def _authenticate(self):
        body = urlencode({
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }).encode("ascii")
        payload = self._request(
            f"{self.login_url}/services/oauth2/token",
            method="POST",
            body=body,
            content_type="application/x-www-form-urlencoded",
            authenticated=False,
        )
        self.access_token = payload["access_token"]
        self.instance_url = payload["instance_url"].rstrip("/")

    def _request(self, url, method="GET", body=None, content_type="application/json",
                 authenticated=True):
        headers = {"Content-Type": content_type, "Accept": "application/json"}
        if authenticated:
            if not self.access_token:
                self._authenticate()
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                response_body = response.read()
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SalesforceError(
                f"Salesforce returned HTTP {error.code}: {detail}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise SalesforceError(f"Could not reach Salesforce: {error}") from error

        if not response_body:
            return {}
        try:
            return json.loads(response_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise SalesforceError("Salesforce returned an invalid response.") from error

    def _api(self, path, method="GET", payload=None):
        if not self.access_token:
            self._authenticate()
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        return self._request(
            f"{self.instance_url}/services/data/{self.api_version}/{path}",
            method=method,
            body=body,
        )

    def _query(self, soql):
        result = self._api(f"query/?{urlencode({'q': soql})}")
        records = result["records"]
        while result.get("nextRecordsUrl"):
            result = self._request(
                f"{self.instance_url}{result['nextRecordsUrl']}"
            )
            records.extend(result["records"])
        return records

    @staticmethod
    def _soql_string(value):
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def sync_order(self, order):
        if not self.configured:
            order.salesforce_sync_status = "not_configured"
            order.salesforce_sync_error = (
                "Set SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET, and "
                "SALESFORCE_ACCOUNT_ID to enable Salesforce sync."
            )
            order.save(update_fields=[
                "salesforce_sync_status", "salesforce_sync_error",
            ])
            return False

        try:
            account_id = self.account_id
            contact_id = order.salesforce_contact_id
            if not contact_id:
                contact_id = self._find_or_create_contact(order, account_id)

            opportunity_id = order.salesforce_opportunity_id
            if not opportunity_id:
                opportunity_id = self._find_or_create_opportunity(order, account_id)
            self._ensure_opportunity_contact_role(contact_id, opportunity_id)
            salesforce_order_id = order.salesforce_order_id
            if not salesforce_order_id:
                salesforce_order_id = self._find_or_create_salesforce_order(
                    order, account_id
                )

            order.salesforce_contact_id = contact_id
            order.salesforce_opportunity_id = opportunity_id
            order.salesforce_order_id = salesforce_order_id
            order.salesforce_sync_status = "synced"
            order.salesforce_sync_error = ""
            order.save(update_fields=[
                "salesforce_contact_id",
                "salesforce_opportunity_id",
                "salesforce_order_id",
                "salesforce_sync_status",
                "salesforce_sync_error",
            ])
            return True
        except (KeyError, TypeError, SalesforceError) as error:
            logger.exception("Salesforce sync failed for order %s", order.reference)
            order.salesforce_sync_status = "failed"
            order.salesforce_sync_error = str(error)
            order.save(update_fields=[
                "salesforce_sync_status", "salesforce_sync_error",
            ])
            return False

    def _find_or_create_contact(self, order, account_id):
        contact = None
        lookup_field = "Email" if order.email else "Phone"
        lookup_value = order.email or order.phone
        if lookup_value:
            records = self._query(
                f"SELECT Id FROM Contact WHERE {lookup_field} = "
                f"'{self._soql_string(lookup_value)}' AND "
                f"AccountId = '{self._soql_string(account_id)}' LIMIT 1"
            )
            if records:
                contact = records[0]["Id"]

        name_parts = order.name.split(maxsplit=1)
        payload = {
            "FirstName": name_parts[0] if len(name_parts) > 1 else None,
            "LastName": name_parts[-1],
            "Email": order.email or None,
            "Phone": order.phone,
            "AccountId": account_id,
        }
        if contact:
            self._api(
                f"sobjects/Contact/{contact}", method="PATCH", payload=payload
            )
            return contact

        return self._api("sobjects/Contact/", method="POST", payload=payload)["id"]

    def _find_or_create_opportunity(self, order, account_id):
        opportunity_name = f"Order {order.reference}"
        records = self._query(
            "SELECT Id FROM Opportunity WHERE Name = "
            f"'{self._soql_string(opportunity_name)}' AND "
            f"AccountId = '{self._soql_string(account_id)}' LIMIT 1"
        )
        if records:
            return records[0]["Id"]

        item_lines = [
            f"{item.quantity} x {item.name} (INR {item.unit_price} each)"
            for item in order.items.all()
        ]
        payload = {
            "Name": opportunity_name,
            "AccountId": account_id,
            "StageName": "Prospecting",
            "CloseDate": order.date.isoformat(),
            "Amount": order.total,
            "Description": (
                f"Shop order {order.reference}; "
                f"{order.get_fulfilment_display()} on {order.date.isoformat()}; "
                f"Items: {', '.join(item_lines)}"
            ),
        }
        return self._api(
            "sobjects/Opportunity/", method="POST", payload=payload
        )["id"]

    def _ensure_opportunity_contact_role(self, contact_id, opportunity_id):
        records = self._query(
            "SELECT Id FROM OpportunityContactRole WHERE "
            f"ContactId = '{self._soql_string(contact_id)}' AND "
            f"OpportunityId = '{self._soql_string(opportunity_id)}' LIMIT 1"
        )
        if not records:
            self._api(
                "sobjects/OpportunityContactRole/",
                method="POST",
                payload={
                    "ContactId": contact_id,
                    "OpportunityId": opportunity_id,
                    "Role": "Decision Maker",
                    "IsPrimary": True,
                },
            )

    def _find_or_create_salesforce_order(self, order, account_id):
        item_lines = [
            f"{item.quantity} x {item.name} at INR {item.unit_price} each"
            for item in order.items.all()
        ]
        description = (
            f"Aysha Pharmacy order {order.reference}; total INR {order.total}; "
            f"{order.get_fulfilment_display()} on {order.date.isoformat()}; "
            f"Products: {', '.join(item_lines)}"
        )
        records = self._query(
            "SELECT Id, Description FROM Order WHERE "
            f"AccountId = '{self._soql_string(account_id)}' AND "
            f"EffectiveDate = {order.date.isoformat()}"
        )
        for record in records:
            if record["Description"] == description:
                return record["Id"]

        payload = {
            "AccountId": account_id,
            "EffectiveDate": order.date.isoformat(),
            "Status": "Draft",
            "Description": description,
        }
        return self._api("sobjects/Order/", method="POST", payload=payload)["id"]


def sync_order_to_salesforce(order):
    return SalesforceClient().sync_order(order)
