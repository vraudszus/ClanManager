import logging
import os.path

import pandas as pd
import numpy as np
import itertools

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from player_ranking.models.clan import Clan
from player_ranking.constants import ROOT_DIR
from player_ranking.models.ranking_parameters import GoogleSheets

LOGGER = logging.getLogger(__name__)
ACCESS_TOKEN_FILENAME: str = ".gsheets_access_token.json"


class GSheetsAPIClient:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, refresh_token: str, spreadsheet_id: str, sheet_names: GoogleSheets) -> None:
        self.access_token_path: str = (ROOT_DIR / ACCESS_TOKEN_FILENAME).as_posix()
        self.spreadsheet_id = spreadsheet_id
        self.service = self.connect_to_service(refresh_token)
        self.sheet_names = sheet_names

    def connect_to_service(self, refresh_token: str):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(self.access_token_path):
            creds = Credentials.from_authorized_user_file(self.access_token_path, self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(refresh_token, self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(self.access_token_path, "w") as token:
                token.write(creds.to_json())

        return build("sheets", "v4", credentials=creds)

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
        request = self.service.spreadsheets().values().clear(spreadsheetId=self.spreadsheet_id, range=sheet_name)
        return request.execute()

    def write_sheet(self, df, sheet_name: str):
        self._clear_sheet(sheet_name)
        csv_string = df.to_csv(sep=";", float_format="%.0f")
        body = {
            "requests": [
                {
                    "pasteData": {
                        "coordinate": {
                            "sheetId": self._get_sheet_id(sheet_name),
                            "rowIndex": "0",
                            "columnIndex": "0",
                        },
                        "data": csv_string,
                        "type": "PASTE_NORMAL",
                        "delimiter": ";",
                    }
                }
            ]
        }
        request = self.service.spreadsheets().batchUpdate(spreadsheetId=self.spreadsheet_id, body=body)
        response = request.execute()
        return response

    def get_excuses(self) -> pd.DataFrame:
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=self.spreadsheet_id, range=self.sheet_names.excuses)
            .execute()
        )
        data = result.get("values", [])
        # pad short rows to prevent mismatch between column header count and data columns
        data = list(zip(*itertools.zip_longest(*data)))
        if len(data) > 0:
            return pd.DataFrame(data[1:], columns=data[0]).set_index("tag")
        else:
            return pd.DataFrame()

    def update_excuse_sheet(self, clan: Clan, current_war, war_history: pd.DataFrame, not_in_clan_str):
        excuses = self.get_excuses()

        def empty_cells_with_numbers(x):
            try:
                float(x)
                return np.nan
            except ValueError:
                return x

        all_tags = clan.get_tags()
        missingFromCurrentWar = pd.Index(all_tags).difference(current_war.index)
        if not missingFromCurrentWar.empty:
            LOGGER.info(f"Missing from current war: {missingFromCurrentWar}")
        goodKeys = current_war.index.intersection(all_tags)
        # goodKeys is needed as some members do not show up in current_war
        # at season begin when not logging in some time after the end the previous war
        current_war = current_war[goodKeys]

        wars = war_history.copy()
        wars.drop(columns="mean", inplace=True)
        wars.insert(0, "current", current_war)
        wars = wars.map(empty_cells_with_numbers)
        missing = excuses.index.difference(wars.index)
        missing_df = pd.DataFrame(index=missing, columns=wars.columns).fillna(not_in_clan_str)
        wars = pd.concat([wars, missing_df])

        try:
            # the column next to current
            last_recorded_cw = excuses.columns.values[2]
        except IndexError:
            last_recorded_cw = -1

        if last_recorded_cw not in war_history.columns.tolist():
            LOGGER.info(f"Replace entire {self.sheet_names.excuses}")
            excuses = wars
        else:
            columns_to_shift = war_history.columns.tolist().index(last_recorded_cw)
            if columns_to_shift > 0:
                LOGGER.info(f"Shift existing {self.sheet_names.excuses} by {columns_to_shift} columns")
                excuses = pd.concat(
                    [
                        excuses.iloc[:, :1],
                        wars.iloc[:, :columns_to_shift],
                        excuses.iloc[:, 1:-columns_to_shift],
                    ],
                    axis=1,
                )
                excuses.columns = wars.columns.insert(0, "name")
                tags_to_remove = excuses[excuses.eq(not_in_clan_str).sum(1) >= 11].index
                if not tags_to_remove.empty:
                    LOGGER.info(f"Removed tags {tags_to_remove.tolist()} from sheet {self.sheet_names.excuses}")
                    excuses.drop(tags_to_remove, inplace=True)
            else:
                LOGGER.info(f"Restore old {self.sheet_names.excuses}")
                for tag in all_tags:
                    # add rows for new players
                    if tag not in excuses.index:
                        excuses.loc[tag] = pd.Series()

        # add names
        excuses.index.name = "tag"
        if "name" not in excuses.columns:
            excuses.insert(loc=0, column="name", value=pd.Series(clan.get_tag_name_map()))
        for tag, _ in excuses[excuses["name"].isna()].iterrows():
            if tag in all_tags:
                excuses.at[tag, "name"] = clan.get(tag).name
        excuses.sort_values(by="name", inplace=True)
        return self.write_sheet(excuses, self.sheet_names.excuses)
