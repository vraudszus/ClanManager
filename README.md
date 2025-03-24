[![Compute Ranking](https://github.com/vraudszus/ClanManager/actions/workflows/compute-ranking.yaml/badge.svg?branch=main)](https://github.com/vraudszus/ClanManager/actions/workflows/compute-ranking.yaml)

# Advanced clan analytics for Clash Royale

- Get detailed insights in the performance of your clan members
- Who performs well? And who doesn't?
- Evaluation criteria can be adjusted to fit your clan's needs
- Get reminded of pending promotions or demotions
- Evaluation can take real life events into account
- Takes input from and outputs to a Google sheet that you can share with your clan

## Example Output

|        | name     |rating | ladder | current_war | war_history | avg_fame | current_season | previous_season |
|--------|----------|--------|--------|-------------|-------------|----------|----------------|-----------------|
| 1     | player1 | 429    | 791    | 1000        | 241         | 2400     | 1306           | 1652            |
| 2     | player2 | 420    | 931    | 912        | 141         | 2255     | 1866           | 1659            |
| 3     | player3 | 409    | 203    | 964        | 472         | 2735     | 777            | 777             |
| 4     | player4 | 408    | 178    | 724        | 493         | 2765     | 1000           | 1511            |
| 5     | player5 | 408    | 330    | 604        | 424         | 2665     | 1508           | 1688            |
| 6     | player6 | 400    | 203    | 757        | 464         | 2722     | 1094           | 1303            |
| 7     | player7 | 399    | 162    | 475        | 486         | 2755     | 1211           | 1680            |
| 8     | player8 | 370    | 291    | 244        | 386         | 2610     | 536            | 1547            |
| 9     | player9 | 367    | 347    | 0        | 359         | 2570     | 975            | 885             |
| 10     | player10 | 338    | 447    | 105        | 272         | 2445     | 0              | 536             |
| mean   |          | 405    | 396    | 579        | 384         | 2607     | 960            | 1146            |
| median |          | 400    | 341    | 664        | 378         | 2598     | 888            | 1432            |

## Prerequisites

- [Python 3.10](https://www.python.org/downloads/) must be installed.
- [Poetry](https://python-poetry.org/docs/#installation) must be installed.
- Install project `$ poetry install` after navigating to the cloned directory.
- To provide the program with the necessary credentials, create a new file `cli-client/.env` with the following contents:

```bash
CR_API_TOKEN=
GSHEET_SPREADSHEET_ID=
GSHEETS_SERVICE_ACCOUNT_KEY=
```

- Add your credentials to `cli-client/.env`
  - `CR_API_TOKEN` [Clash Royale API token](https://developer.clashroyale.com/#/)
    (use the [RoyalAPI proxy](https://docs.royaleapi.com/proxy.html) unless you have a static IP)
  - `GSHEET_SPREADSHEET_ID` ID of a Google spreadsheet with two empty sheets named after
  `googleSheets.rating` and `googleSheets.excuses` in [ranking_parameters.yaml](cli-client/ranking_parameters.yaml)
  - `GSHEETS_SERVICE_ACCOUNT_KEY` The Google Sheets API credentials for writing results to the Google sheet.
    You can obtain the credential by performing steps 1-3 from [this](https://genezio.com/deployment-platform/blog/google-sheets-as-apis/#step-2-create-a-service-account-and-generate-a-key-file)
    guide. You need to grant the service account editor permissions.
    Copy&Paste the contents of the downloaded `.json` file to this variable.

## Usage

First, make sure to update the value of `clanTag` in [ranking_parameters.yaml](cli-client/ranking_parameters.yaml)
and customize the remaining settings to your liking.

    Example usage:
        poetry run player-ranking
        poetry run player-ranking -p
        poetry run player-ranking --plot

    Options:
        -p --plot
        Use this flag to enable plotting of the rating history.
        The resulting image will be saved to the path specified in the properties.

For Windows users, [PlayerRanking.bat](cli-client/PlayerRanking.bat) provides a convenient, double-clickable script
to run through the common use case of updating the ranking, checking the results in Google Sheets,
and rerunning the ranking computation after adding new excused in the Google Sheet.

## Evaluation criteria customization

Using the `ranking_parameters.yaml` file you can customize:

- The clan you want to check
- The weights the rating should apply to different metrics
- The promotion and demotion suggestion criteria
- The different excuses the rating should take into account
- The wars you want to ignore during ranking
- The names of the Google Sheets used to output the results
