import os.path
import pandas as pd
import numpy as np
import itertools

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def connect_to_service(credentials_path, token_path):
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    
    return build("sheets", "v4", credentials=creds)

def get_sheet_by_name(sheet_name, service, spreadsheet_id):
    sheets_with_properties = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields='sheets.properties').execute().get('sheets')
    for sheet in sheets_with_properties:
        if 'title' in sheet['properties'].keys():
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']

def clear_sheet(sheet_name, service, spreadsheet_id):
    request = service.spreadsheets().values().clear(spreadsheetId=spreadsheet_id, range=sheet_name)
    return request.execute()

def write_df_to_sheet(df, sheet_name, spreadsheet_id, service):
    clear_sheet(sheet_name, service, spreadsheet_id)
    csv_string = df.to_csv(sep = ";", float_format= "%.0f")
    body = {
        'requests': [{
            'pasteData': {
                "coordinate": {
                    "sheetId": get_sheet_by_name(sheet_name, service, spreadsheet_id),
                    "rowIndex": "0",
                    "columnIndex": "0",
                },
                "data": csv_string,
                "type": 'PASTE_NORMAL',
                "delimiter": ';',
            }
        }]
    }
    request = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body)
    response = request.execute()
    return response

def get_excuses(sheet_name, service, spreadsheet_id):                        
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=sheet_name).execute()
    data = result.get('values', [])
    # pad short rows to prevent mismatch between column header count and data columns
    data = list(zip(*itertools.zip_longest(*data)))
    if len(data) > 0:
        return pd.DataFrame(data[1:], columns=data[0]).set_index("tag")
    else:
        return pd.DataFrame()

def update_excuse_sheet(members, current_war, war_history, not_in_clan_str, sheet_name, service, spreadsheet_id):
    excuses = get_excuses(sheet_name, service, spreadsheet_id)
    
    def empty_cells_with_numbers(x):
        try:
            float(x)
            return np.nan
        except ValueError:
            return x
    
    current_war = current_war[members.keys()]
    wars = war_history.copy()
    wars.drop(columns="mean", inplace=True)
    wars.insert(0, "current", current_war)
    wars.fillna(not_in_clan_str, inplace=True)
    wars = wars.applymap(empty_cells_with_numbers)
    missing = excuses.index.difference(wars.index)
    missing_df = pd.DataFrame(index=missing, columns=wars.columns).fillna(not_in_clan_str)
    wars = pd.concat([wars, missing_df])
    
    try:
        last_recorded_cw = excuses.columns.values[2] # the column next to current
    except IndexError:
        last_recorded_cw = -1
    
    if last_recorded_cw not in war_history.columns.tolist():
        print("Write complety new", sheet_name)
        excuses = wars
    else:
        columns_to_shift = war_history.columns.tolist().index(last_recorded_cw)
        if columns_to_shift > 0:
            print("Shift existing", sheet_name, "by", columns_to_shift, "columns")
            excuses = pd.concat([excuses.iloc[:,:1], wars.iloc[:, :columns_to_shift], excuses.iloc[:,1:-columns_to_shift]], axis=1)
            excuses.columns = wars.columns.insert(0,"name")
            tags_to_remove = excuses[excuses.eq(not_in_clan_str).sum(1) >= 11].index
            if not tags_to_remove.empty:
                print(", ".join(tags_to_remove.tolist()), "removed from", sheet_name)
                excuses.drop(tags_to_remove, inplace=True)
        else:
            print("Restore old", sheet_name)
            for tag in members:
                # add rows for new players
                if tag not in excuses.index:
                    excuses = excuses.append(pd.Series(name=tag))
    
    # add names
    excuses.index.name = "tag"
    if "name" not in excuses.columns:
        tag_name_map = {k: v["name"] for k,v in members.items()}
        excuses.insert(loc=0, column="name", value=pd.Series(tag_name_map))
    for tag, _ in excuses[excuses["name"].isna()].iterrows():
        if tag in members:
            excuses.at[tag,"name"] = members[tag]["name"]
    excuses.sort_values(by="name", inplace=True)
    return write_df_to_sheet(excuses, sheet_name, spreadsheet_id, service)
