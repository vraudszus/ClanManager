# The best ClanManager for Supercell's game "Clash Royale"

- Get detailed insights in the performance of your clan members
- Who performs well? And who doesn't?
- Evaluation criteria can be adjusted to fit your clan's needs
- Get reminded of pending promotions or demotions
- Evaluation can take real life events into account
- Takes input from and outputs to a Google sheet that you can share with your clan

## Prerequisites

- Python 3.x must be installed.
- Required packages must be installed `$ pip install -r requirements.txt`.
- A token for the Clash Royale API stored in `API-token.txt` in the root folder of this project.
    - Head over to https://developer.clashroyale.com/#/ to create such a token for the IP address `45.79.218.79` of the proxy server.
    - To avoid difficulties caused by dynamic IP addresses this tool uses the proxy provided by [RoyaleAPI](https://docs.royaleapi.com/#/). If you do not want to use the proxy, look into the `properties.yaml` file.
- To use Google Sheets you need a Google account. Then follow these steps:
    1. Create a Google Cloud project by following [this](https://developers.google.com/workspace/guides/create-project) guide and [activate](https://developers.google.com/workspace/guides/enable-apis) the "Google Sheets API".
    2. Create OAuth client ID credentials by following [this](https://developers.google.com/workspace/guides/create-credentials#oauth-client-id) guide. Make sure to add you Google account as a "test user". Download the credentials in JSON format. Place the file in the root folder of this project and rename it to `credentials.json`.
    3. When running the tool for the first time a browser window will ask you to login into a Google account. Use on of the "test user" accounts. This will create the `token.json` file that the app needs to access the Google sheet.
    4. Manually create a new spreadsheet in Google Sheets and paste the `spreadSheetId` in the `gsheet_spreadsheet_id` field in `properties.yaml` ([How to find the spreadsheetId](gsheet_spreadsheet_id)).

## Usage

    Example usage:
        python player-ranking.py 
        python player-ranking.py --ignore_wars -1
        python player-ranking.py --ignore_wars -4 -5 -7
    
    Options:
        --ignore_wars           followed by a number of integers in the range [-1, -10]
        Ignore completed river races during the rating computation. 
        Parameter "-n" describes the n-th last completed river race. 
        E.g. -1 describes the river race from last week.    

## Evaluation criteria customization

Using the `properties.yaml` file you can customize:

- The clan you want to check
- The weights the rating should apply to different metrics
- The promotion and demotion suggestion criteria
- The different excuses the rating should take into account
- The paths of the API token files
- The names of the output Google Sheet, tables, and files

