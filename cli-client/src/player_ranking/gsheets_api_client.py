import itertools
import json
import logging
from json import JSONDecodeError

import numpy as np
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build

from player_ranking.models.clan import Clan
from player_ranking.models.ranking_parameters import GoogleSheets

LOGGER = logging.getLogger(__name__)


class GSheetsAPIClient:
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

    def __init__(self, service_account_key: str, spreadsheet_id: str, sheet_names: GoogleSheets) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.service = self.connect_to_service(service_account_key)
        self.sheet_names = sheet_names

    @staticmethod
    def connect_to_service(service_account_key: str):
        try:
            service_account_key = json.loads(service_account_key)
        except JSONDecodeError as e:
            raise EnvironmentError(f"Unable to parse gsheets service account key: {e}")
        creds = service_account.Credentials.from_service_account_info(service_account_key)
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

    def update_excuse_sheet(
        self, clan: Clan, current_war: pd.Series, war_history: pd.DataFrame, not_in_clan_excuse: str
    ):
        excuses = self.get_excuses()

        all_tags = clan.get_tags()
        wars = self._pad_wars_with_current_war_and_former_members(
            all_tags, current_war, war_history, excuses, not_in_clan_excuse
        )

        # remove not in clan excuses for players that have since rejoined
        excuses.loc[excuses.index.isin(clan.get_tags()) & (excuses["current"] == not_in_clan_excuse), "current"] = ""

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
                excuses = self._prepend_missing_wars_to_excuses(columns_to_shift, excuses, wars, not_in_clan_excuse)
            else:
                LOGGER.info(f"Restore old {self.sheet_names.excuses}")
                self._add_rows_for_new_players(excuses, all_tags)

        self._format_excuses_for_display(excuses, clan)
        return self.write_sheet(excuses, self.sheet_names.excuses)

    @staticmethod
    def _pad_wars_with_current_war_and_former_members(
        all_tags: list[str],
        current_war: pd.Series,
        war_history: pd.DataFrame,
        excuses: pd.DataFrame,
        not_in_clan_excuse: str,
    ) -> pd.DataFrame:
        def empty_cells_with_numbers(x):
            try:
                float(x)
                return np.nan
            except ValueError:
                return x

        missing_from_current_war = pd.Index(all_tags).difference(current_war.index)
        if not missing_from_current_war.empty:
            LOGGER.warning(f"Missing from current war: {missing_from_current_war}")
        good_keys = current_war.index.intersection(all_tags)
        # good_keys is needed as some members do not show up in current_war
        # at season begin when not logging in some time after the end the previous war
        current_war = current_war[good_keys]

        wars = war_history.copy()
        wars.drop(columns="mean", inplace=True)
        wars.insert(0, "current", current_war)
        wars = wars.map(empty_cells_with_numbers)
        missing = excuses.index.difference(wars.index)
        missing_df = pd.DataFrame(index=missing, columns=wars.columns).fillna(not_in_clan_excuse)
        return pd.concat([wars, missing_df])

    def _prepend_missing_wars_to_excuses(
        self, columns_to_shift: int, excuses: pd.DataFrame, wars: pd.DataFrame, not_in_clan_excuse: str
    ) -> pd.DataFrame:
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
        tags_to_remove = excuses[excuses.eq(not_in_clan_excuse).sum(1) >= 11].index
        if not tags_to_remove.empty:
            LOGGER.info(f"Removed tags {tags_to_remove.tolist()} from sheet {self.sheet_names.excuses}")
            excuses.drop(tags_to_remove, inplace=True)
        return excuses

    @staticmethod
    def _add_rows_for_new_players(excuses: pd.DataFrame, all_tags: list[str]) -> None:
        for tag in all_tags:
            if tag not in excuses.index:
                excuses.loc[tag] = pd.Series()

    @staticmethod
    def _format_excuses_for_display(excuses: pd.DataFrame, clan: Clan) -> None:
        if "name" not in excuses.columns:
            excuses.insert(loc=0, column="name", value=pd.Series(clan.get_tag_name_map()))
        for tag, _ in excuses[excuses["name"].isna()].iterrows():
            if tag in clan.get_tags():
                excuses.at[tag, "name"] = clan.get(tag).name

        excuses.index.name = "tag"
        excuses.sort_values(by="name", inplace=True)
