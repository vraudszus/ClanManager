import os.path
from matplotlib.pyplot import cla
import pandas as pd
import numpy as np

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TOKEN_PATH = "token.json"
SPREADSHEET_ID = "1bVKGKJOIT6V8BSNRWpt24Ha8fVRXM1xjYluqx-U-N1Q"
NOT_IN_CLAN = "nicht im Clan"

def connect_to_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    
    return build("sheets", "v4", credentials=creds)

def get_sheet_by_name(sheet_name, service):
    sheets_with_properties = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID, fields='sheets.properties').execute().get('sheets')

    for sheet in sheets_with_properties:
        if 'title' in sheet['properties'].keys():
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']

def write_player_ranking(df, sheet_id, service):
    csv_string = df.to_csv(sep = ";", float_format= "%.3f")
    body = {
        'requests': [{
            'pasteData': {
                "coordinate": {
                    "sheetId": sheet_id,
                    "rowIndex": "0",
                    "columnIndex": "0",
                },
                "data": csv_string,
                "type": 'PASTE_NORMAL',
                "delimiter": ';',
            }
        }]
    }
    request = service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body)
    response = request.execute()
    return response

def get_excuses(sheet_name, service):                        
    result = service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=sheet_name).execute()
    data = result.get('values', [])
    if len(data) > 0:
        return pd.DataFrame(data[1:], columns=data[0]).set_index("")
    else:
        return pd.DataFrame()    

import requests
import json
clanTag = "#GP9GRQ"
apiToken = open("API-token.txt", "r").read()
baseURL = "https://proxy.royaleapi.dev/v1" # URL of proxy from RoyaleAPI

headers = {}
headers["Accept"] = "application/json"
headers["authorization"] = f"Bearer {apiToken}"

# def get_war_statistics(clan_tag, members):
#     api_call = f"/clans/%23{clan_tag[1:]}/riverracelog"
#     response = requests.get(baseURL + api_call, headers = headers)
#     river_races = json.loads(response.text)["items"]

#     war_statistics = {}
#     for player_tag in members.keys():
#         war_statistics[player_tag] = {}

#     for river_race in river_races:
#         river_race_id = f'{river_race["seasonId"]}.{river_race["sectionIndex"]}'
#         standings = river_race["standings"]
#         for standing in standings:
#             clan = standing["clan"]
#             if clan["tag"] == clanTag:
#                 for participant in clan["participants"]:
#                     player_tag = participant["tag"]
#                     if player_tag in war_statistics:
#                         war_statistics[player_tag][river_race_id] = int(participant["fame"])
#     return pd.DataFrame.from_dict(war_statistics, orient = "index")

# def get_current_river_race(clan_tag):
#     api_call = f"/clans/%23{clan_tag[1:]}/currentriverrace"
#     response = requests.get(baseURL + api_call, headers = headers)
#     clan = json.loads(response.text)["clan"]

#     current_war_statistics = {}
#     for participant in clan["participants"]:
#         player_tag = participant["tag"]
#         current_war_statistics[player_tag] = int(participant["fame"])
#     return pd.Series(current_war_statistics)

# def get_current_members(clan_tag):
#     api_call = f"/clans/%23{clan_tag[1:]}"
#     response = requests.get(baseURL + api_call, headers = headers)
#     member_list = json.loads(response.text)["memberList"]
#     members = {}
#     for member in member_list:
#         info = {
#             "name": member["name"],
#             "role": member["role"],
#         }
#         members[member["tag"]] = info
#     return members

def update_excuse_sheet(members, current_war, war_history, sheet_name, service):
    old_df = get_excuses(sheet_name, service)
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
    missing_series = pd.Series(index=cur_missing, dtype=str).fillna(NOT_IN_CLAN)
    current_war = current_war.append(missing_series)
    
    war_history = war_history.fillna(NOT_IN_CLAN)
    war_history.index = war_history.index.map(lambda x: members[x]["name"])
    war_history = war_history.applymap(isnumber)
    war_missing = old_df.index.difference(war_history.index)
    missing_df = pd.DataFrame(index=war_missing, columns=war_history.columns).fillna(NOT_IN_CLAN)
    war_history = pd.concat([war_history, missing_df])
    
    try:
        last_finished_cw = old_df.columns.values[1] # the column next to current
    except IndexError:
        last_finished_cw = -1
    new_df = None
    if last_finished_cw not in war_history.columns.tolist():
        new_df = pd.concat([current_war, war_history], axis=1)
        new_df = new_df.rename(columns={0: "current"})
    else:
        columns_to_shift = war_history.columns.tolist().index(last_finished_cw)
        if columns_to_shift >= 1:
            new_df = pd.concat([current_war, war_history.iloc[:, :columns_to_shift-1], old_df], axis=1)
            new_df = new_df.rename(columns={"current": war_history.columns.tolist()[columns_to_shift-1]})
            new_df = new_df.rename(columns={0: "current"})
            new_df = new_df.drop(new_df[new_df.eq(NOT_IN_CLAN).sum(1) >= 11].index)
        else:
            new_df = old_df
    
    csv_string = new_df.to_csv(sep = ";")
    body = {
        'requests': [{
            'pasteData': {
                "coordinate": {
                    "sheetId": get_sheet_by_name(sheet_name, service),
                    "rowIndex": "0",
                    "columnIndex": "0",
                },
                "data": csv_string,
                "type": 'PASTE_NORMAL',
                "delimiter": ';',
            }
        }]
    }
    request = service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body=body)
    response = request.execute()
    return response
    
#service = connect_to_service()
#write_player_ranking(pd.read_csv("player-ranking.csv", sep=";"), get_sheet_by_name("PlayerRanking", service), service)
#update_excuse_sheet(get_current_members(clanTag), get_current_river_race(clanTag), get_war_statistics(clanTag, get_current_members(clanTag)), "Abmeldungen", service)