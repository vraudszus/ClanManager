import os.path
import pandas as pd
import numpy as np
import itertools

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


class GSheetsWrapper:

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self, credentialsPath: str, tokenPath: str, spreadSheetIdPath: str) -> None:
        self.service = self.connect_to_service(credentialsPath, tokenPath)
        self.spreadSheetId = open(spreadSheetIdPath, "r").read()

    def connect_to_service(self, credentials_path: str, token_path: str):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("sheets", "v4", credentials=creds)

    def _get_sheet_by_name(self, sheet_name: str):
        sheets_with_properties = self.service.spreadsheets().get(
            spreadsheetId=self.spreadSheetId, fields='sheets.properties').execute().get('sheets')
        for sheet in sheets_with_properties:
            if 'title' in sheet['properties'].keys():
                if sheet['properties']['title'] == sheet_name:
                    return sheet['properties']['sheetId']

    def _clear_sheet(self, sheet_name: str):
        request = self.service.spreadsheets().values().clear(
            spreadsheetId=self.spreadSheetId, range=sheet_name)
        return request.execute()

    def write_df_to_sheet(self, df, sheet_name: str):
        self._clear_sheet(sheet_name)
        csv_string = df.to_csv(sep=";", float_format="%.0f")
        body = {
            'requests': [{
                'pasteData': {
                    "coordinate": {
                        "sheetId": self._get_sheet_by_name(sheet_name),
                        "rowIndex": "0",
                        "columnIndex": "0",
                    },
                    "data": csv_string,
                    "type": 'PASTE_NORMAL',
                    "delimiter": ';',
                }
            }]
        }
        request = self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.spreadSheetId, body=body)
        response = request.execute()
        return response

    def get_excuses(self, sheet_name: str) -> pd.DataFrame:
        result = self.service.spreadsheets().values().get(
            spreadsheetId=self.spreadSheetId, range=sheet_name).execute()
        data = result.get('values', [])
        # pad short rows to prevent mismatch between column header count and data columns
        data = list(zip(*itertools.zip_longest(*data)))
        if len(data) > 0:
            return pd.DataFrame(data[1:], columns=data[0]).set_index("tag")
        else:
            return pd.DataFrame()

    def update_excuse_sheet(self, members, current_war, war_history, not_in_clan_str, sheet_name):
        excuses = self.get_excuses(sheet_name)

        def empty_cells_with_numbers(x):
            try:
                float(x)
                return np.nan
            except ValueError:
                return x
        missingFromCurrentWar = pd.Index(members.keys()).difference(current_war.index)
        if not missingFromCurrentWar.empty:
            print("Missing from current war:", missingFromCurrentWar)
        goodKeys = current_war.index.intersection(members.keys())
        # goodKeys is needed as some members do not show up in current_war
        # at season begin when not logging in some time after the end the previous war
        current_war = current_war[goodKeys]

        wars = war_history.copy()
        wars.drop(columns="mean", inplace=True)
        wars.insert(0, "current", current_war)
        wars.fillna(not_in_clan_str, inplace=True)
        wars = wars.applymap(empty_cells_with_numbers)
        missing = excuses.index.difference(wars.index)
        missing_df = pd.DataFrame(
            index=missing, columns=wars.columns).fillna(not_in_clan_str)
        wars = pd.concat([wars, missing_df])

        try:
            # the column next to current
            last_recorded_cw = excuses.columns.values[2]
        except IndexError:
            last_recorded_cw = -1

        if last_recorded_cw not in war_history.columns.tolist():
            print("Write complety new", sheet_name)
            excuses = wars
        else:
            columns_to_shift = war_history.columns.tolist().index(last_recorded_cw)
            if columns_to_shift > 0:
                print("Shift existing", sheet_name, "by", columns_to_shift, "columns")
                excuses = pd.concat([excuses.iloc[:, :1], wars.iloc[:, :columns_to_shift],
                                    excuses.iloc[:, 1:-columns_to_shift]], axis=1)
                excuses.columns = wars.columns.insert(0, "name")
                tags_to_remove = excuses[excuses.eq(
                    not_in_clan_str).sum(1) >= 11].index
                if not tags_to_remove.empty:
                    print(", ".join(tags_to_remove.tolist()), "removed from", sheet_name)
                    excuses.drop(tags_to_remove, inplace=True)
            else:
                print("Restore old", sheet_name)
                for tag in members:
                    # add rows for new players
                    if tag not in excuses.index:
                        excuses = pd.concat(excuses, pd.Series(name=tag))

        # add names
        excuses.index.name = "tag"
        if "name" not in excuses.columns:
            tag_name_map = {k: v["name"] for k, v in members.items()}
            excuses.insert(loc=0, column="name", value=pd.Series(tag_name_map))
        for tag, _ in excuses[excuses["name"].isna()].iterrows():
            if tag in members:
                excuses.at[tag, "name"] = members[tag]["name"]
        excuses.sort_values(by="name", inplace=True)
        return self.write_df_to_sheet(excuses, sheet_name)
