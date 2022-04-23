import os.path
import pandas as pd
import numpy as np

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

def write_player_ranking(df, sheet_name, service, spreadsheet_id):
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
    if len(data) > 0:
        return pd.DataFrame(data[1:], columns=data[0]).set_index("")
    else:
        return pd.DataFrame()

def update_excuse_sheet(members, current_war, war_history, not_in_clan_str, sheet_name, service, spreadsheet_id):
    old_df = get_excuses(sheet_name, service, spreadsheet_id)
    clear_sheet(sheet_name, service, spreadsheet_id)
    def isnumber(x):
        try:
            float(x)
            return np.nan
        except ValueError:
            return x
        
    current_war = current_war[members.keys()]
    current_war.index = current_war.index.map(lambda x: members[x]["name"])
    current_war = current_war.apply(isnumber)
    cur_missing = old_df.index.difference(current_war.index)
    missing_series = pd.Series(index=cur_missing, dtype=str).fillna(not_in_clan_str)
    current_war = current_war.append(missing_series)
    
    war_history = war_history.iloc[:, :10] # remove mean column
    war_history = war_history.fillna(not_in_clan_str)
    war_history.index = war_history.index.map(lambda x: members[x]["name"])
    war_history = war_history.applymap(isnumber)
    war_missing = old_df.index.difference(war_history.index)
    missing_df = pd.DataFrame(index=war_missing, columns=war_history.columns).fillna(not_in_clan_str)
    war_history = pd.concat([war_history, missing_df])
    
    try:
        last_finished_cw = old_df.columns.values[1] # the column next to current
    except IndexError:
        last_finished_cw = -1
    new_df = None
    if last_finished_cw not in war_history.columns.tolist():
        new_df = pd.concat([current_war, war_history], axis=1)
        new_df = new_df.rename(columns={0: "current"})
        print("Write complety new", sheet_name)
    else:
        columns_to_shift = war_history.columns.tolist().index(last_finished_cw)
        if columns_to_shift >= 1:
            new_df = pd.concat([current_war, war_history.iloc[:, :columns_to_shift-1], old_df], axis=1)
            new_df = new_df.rename(columns={"current": war_history.columns.tolist()[columns_to_shift-1]})
            new_df = new_df.rename(columns={0: "current"})
            new_df = new_df.drop(new_df[new_df.eq(not_in_clan_str).sum(1) >= 11].index)
            print("Shift existing", sheet_name, "by", columns_to_shift, "columns")
        else:
            new_df = old_df
            print("Restore old", sheet_name)
            
        for tag in members:
            # add rows for new players
            name = members[tag]["name"]
            if name not in new_df.index:
                new_df = new_df.append(pd.Series(name=name))
            
    new_df.sort_index(inplace=True)
    csv_string = new_df.to_csv(sep = ";")
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
