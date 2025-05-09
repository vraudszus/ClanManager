import yaml
import pandas as pd
import matplotlib.pyplot as plt

from player_ranking import cr_api_client

props = yaml.safe_load(open("ranking_parameters.yaml", "r"))
clan_tag = props["clanTag"]
cr_token = props["apiTokens"]["crApiTokenPath"]
rating_history_file = props["ratingHistoryFile"]

clan = cr_api_client.get_current_members(clan_tag, cr_token)

df = pd.read_csv(rating_history_file, sep=";", index_col=0)
onlyCurrentMembers = df.loc[clan.get_tags()]

for tag, datapoints in onlyCurrentMembers.iterrows():
    for date, score in datapoints.items():
        if pd.notna(score):
            onlyCurrentMembers.at[tag, "firstSighting"] = date
            break

firstSightings = pd.to_datetime(onlyCurrentMembers["firstSighting"], format="%d.%m.%Y %H:%M:%S")
print(firstSightings)

print("newest", firstSightings.max())
print("oldest", firstSightings.min())
print("mean", firstSightings.mean())
print("median", firstSightings.median())

byMonth = firstSightings.groupby([firstSightings.dt.year, firstSightings.dt.month]).count()
byMonth.index = map(lambda i: f"{i[1]}.{i[0]}", byMonth.index)
print(byMonth)
byMonth.plot(kind="bar")
plt.tight_layout()
plt.savefig("FirstSighting.png")
plt.show()
