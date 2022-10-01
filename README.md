# The best ClanManager for Supercell's Clash Royale

- Get detailed insights in the performance of your clan members
- Who performs well? And who doesn't?
- Evaluation criteria can be adjusted to fit your clan's needs
- Get reminded of pending promotions or demotions
- Evaluation can take real life events into account
- Takes input from and outputs to a Google sheet that you can share with your clan

## Example Output (manually shortened and anonymized)

|        | name     | role     | rating | current_season | previous_season | current_war | war_history | avg_fame | ladder_rank |
|--------|----------|----------|--------|----------------|-----------------|-------------|-------------|----------|-------------|
| 1     | player1 | member   | 429    | 791            | 740             | 1000        | 241         | 2400     | 5           |
| 2     | player2 | elder    | 420    | 931            | 952             | 912        | 141         | 2255     | 4           |
| 3     | player3 | elder    | 409    | 203            | 515             | 964        | 472         | 2735     | 36          |
| 4     | player4 | elder    | 408    | 178            | 427             | 724        | 493         | 2765     | 45          |
| 5     | player5 | elder    | 408    | 330            | 495             | 604        | 424         | 2665     | 34          |
| 6     | player6 | elder    | 400    | 203            | 476             | 757        | 464         | 2722     | 41          |
| 7     | player7 | elder    | 399    | 162            | 427             | 475        | 486         | 2755     | 40          |
| 8     | player8 | coLeader | 370    | 291            | 465             | 244        | 386         | 2610     | 25          |
| 9     | player9 | elder    | 367    | 347            | 476             | 0        | 359         | 2570     | 18          |
| 10     | player10 | elder    | 338    | 447            | 498             | 105        | 272         | 2445     | 19          |
| mean   |          |          | 405    | 396            | 563             | 579        | 384         | 2607     | 26          |
| median |          |          | 400    | 341            | 510             | 664        | 378         | 2598     | 26          |

## Prerequisites

- Python 3.x must be installed.
- Required packages must be installed `$ pip install -r requirements.txt`.
- A token for the Clash Royale API stored in `API-token.txt` in the root folder of this project.
    - Head over to https://developer.clashroyale.com/#/ to create such a token for the IP address `45.79.218.79` of the proxy server.
    - To avoid difficulties caused by dynamic IP addresses this tool uses the proxy provided by [RoyaleAPI](https://docs.royaleapi.com/#/). If you do not want to use the proxy, look into the `properties.yaml` file.
- To use Google Sheets you need a Google account. Then follow these steps:
    1. Create a Google Cloud project by following [this](https://developers.google.com/workspace/guides/create-project) guide and [activate](https://developers.google.com/workspace/guides/enable-apis) the "Google Sheets API".
    2. Create OAuth client ID credentials by following [this](https://developers.google.com/workspace/guides/create-credentials#oauth-client-id) guide. Make sure to add you Google account as a "test user". Download the credentials in JSON format. Place the file in the root folder of this project and rename it to `credentials.json`.
    3. When running the tool for the first time a browser window will ask you to login into a Google account. Use one of the "test user" accounts. This will create the `token.json` file that the app needs to access the Google sheet.
    4. Manually create a new spreadsheet in Google Sheets and paste the `spreadSheetId` in a new file called `gSpreadsheetId.txt` in the root folder of the project ([How to find the spreadsheetId](gsheet_spreadsheet_id)).
    5. Add two empty sheets to your new Google spreadsheet. Rename the sheets to the values of `rating` and `excuses` in the `properties.yaml` file under `googleSheets`.

## Usage

First, make sure to update the value of `clanTag` in `properties.yaml` and customize the rating settings to your liking.

    Example usage:
        python -m playerRanking
        python -m playerRanking -p
        python -m playerRanking --plot

    Options:
        -p --plot
        Use this flag to enable plotting of the rating history. 
        The resulting image will be saved to the path specified in the properties.

## Evaluation criteria customization

Using the `properties.yaml` file you can customize:

- The clan you want to check
- The weights the rating should apply to different metrics
- The promotion and demotion suggestion criteria
- The different excuses the rating should take into account
- The wars you want to ignore during ranking
- The paths of the API token files
- The names of the output Google Sheet, tables, and files
