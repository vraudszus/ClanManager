import itertools
import json
import logging
import random
import time
from json import JSONDecodeError
from typing import Callable, Any

import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
        response = self.execute_with_retry(lambda: request.execute(), f"write_sheet_{sheet_name}")
        return response

    def fetch_sheet(self, sheet_name: str) -> pd.DataFrame:
        request = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=sheet_name)
        )
        result = self.execute_with_retry(lambda: request.execute(), f"fetch_sheet_{sheet_name}")
        data = result.get("values", [])
        # pad short rows to prevent mismatch between column header count and data columns
        data = list(zip(*itertools.zip_longest(*data)))
        if len(data) > 0:
            return pd.DataFrame(data[1:], columns=data[0]).set_index("tag")
        else:
            return pd.DataFrame()

    def _get_sheet_id(self, sheet_name: str):
        request = self.service.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id, fields="sheets.properties"
        )
        response = self.execute_with_retry(lambda: request.execute(), f"get_sheet_{sheet_name}")
        sheets_with_properties = response.get("sheets")
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
        return self.execute_with_retry(lambda: request.execute(), f"clear_sheet_{sheet_name}")

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

    @staticmethod
    def execute_with_retry(func: Callable[[], Any], op_name: str, max_retries: int = 5) -> Any:
        for attempt in range(max_retries):
            try:
                return func()
            except HttpError as e:
                if e.resp.status in [500, 503]:
                    delay = 2**attempt + random.uniform(0, 1)

                    LOGGER.warning(
                        "[%s] Retry %d/%d after %.2fs (error=%s)",
                        op_name,
                        attempt + 1,
                        max_retries,
                        delay,
                        e,
                    )

                    time.sleep(delay)
                else:
                    raise  # rethrow non-retryable errors

        raise Exception(f"Max retries {max_retries} exceeded for operation {op_name}")
