import itertools
import json
import logging
from json import JSONDecodeError

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

LOGGER = logging.getLogger(__name__)


class GSheetsAPIClient:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, service_account_key: str, spreadsheet_id: str) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.service = self._connect_to_service(service_account_key)

    def write_sheet(self, df, sheet_name: str):
        self._clear_sheet(sheet_name)
        values = self._df_to_sheets_values(df)
        request = (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self.spreadsheet_id,
                range=sheet_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
        )
        response = request.execute()
        return response

    def fetch_sheet(self, sheet_name: str) -> pd.DataFrame:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=sheet_name)
            .execute()
        )
        data = result.get("values", [])
        # pad short rows to prevent mismatch between column header count and data columns
        data = list(zip(*itertools.zip_longest(*data)))
        if len(data) > 0:
            return pd.DataFrame(data[1:], columns=data[0]).set_index("tag")
        else:
            return pd.DataFrame()

    def _get_sheet_id(self, sheet_name: str):
        sheets_with_properties = (
            self.service.spreadsheets()
            .get(spreadsheetId=self.spreadsheet_id, fields="sheets.properties")
            .execute()
            .get("sheets")
        )
        for sheet in sheets_with_properties:
            if sheet["properties"]["title"] == sheet_name:
                return sheet["properties"]["sheetId"]
        raise KeyError(f"Sheet {sheet_name} not found in Google spreadsheet.")

    def _clear_sheet(self, sheet_name: str):
        request = (
            self.service.spreadsheets()
            .values()
            .clear(spreadsheetId=self.spreadsheet_id, range=sheet_name)
        )
        return request.execute()

    @staticmethod
    def _df_to_sheets_values(df: pd.DataFrame) -> list[list[str]]:
        """
        Convert a DataFrame to a list-of-lists suitable for Google Sheets API values.update.
        - All numbers are formatted as integers (like float_format="%.0f").
        """
        # Reset index so it becomes a column
        df_reset = df.reset_index()

        def clean_value(x):
            if pd.isna(x):
                return ""
            if isinstance(x, float):
                return int(x)
            return x

        cleaned = df_reset.map(clean_value)

        # Create header row (index name + column names)
        header = cleaned.columns.tolist()

        values = [header] + cleaned.values.tolist()
        return values

    @staticmethod
    def _connect_to_service(service_account_key: str):
        try:
            service_account_key = json.loads(service_account_key)
        except JSONDecodeError as e:
            raise EnvironmentError(f"Unable to parse gsheets service account key: {e}")
        creds = service_account.Credentials.from_service_account_info(service_account_key)
        return build("sheets", "v4", credentials=creds)
