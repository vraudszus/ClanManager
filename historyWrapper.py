from datetime import timedelta, datetime
import pandas as pd
import matplotlib.pyplot as plt
from labellines import labelLines
from cycler import cycler

DATETIME_FORMAT = "%d.%m.%Y %H:%M:%S"


def append_rating_history(rating_history_path: str, rating: pd.DataFrame):
    now = datetime.utcnow()
    rating.rename(now.strftime(DATETIME_FORMAT), inplace=True)
    try:
        rating_history = pd.read_csv(rating_history_path, sep=";", index_col=0)
        rating_history = pd.concat([rating_history, rating], axis=1)
    except FileNotFoundError:
        rating_history = rating.to_frame()
    rating_history.to_csv(rating_history_path, sep=";", float_format="%.0f")


def filter_close_timestamps(rating_history: pd.DataFrame):
    columns_to_drop = []
    for i, timestamp in enumerate(rating_history.columns):
        if i > 0 and timestamp - rating_history.columns[i-1] < timedelta(hours=6):
            columns_to_drop.append(rating_history.columns[i-1])
    rating_history.drop(columns_to_drop, inplace=True, axis="columns")
    return rating_history


def plot_rating_history(rating_history_path: str, members: dict, rating_history_image: str):
    # Only plots current clan members
    rating_history = pd.read_csv(rating_history_path, sep=";", index_col=0)

    rating_history.columns = pd.to_datetime(rating_history.columns, format=DATETIME_FORMAT)
    rating_history = filter_close_timestamps(rating_history)
    rating_history = rating_history.loc[members.keys()]
    rating_history.index = [members[tag]["name"] for tag in rating_history.index]
    rating_history = rating_history.T

    fig = plt.figure()
    ax = fig.add_subplot(111)
    colormap = list(plt.cm.tab20.colors)
    del colormap[4-1::4]  # Delete every 4th color
    prop_cycle = cycler(color=colormap) * cycler(linestyle=["-", ":", "--", "-."])
    ax.set_prop_cycle(prop_cycle)
    rating_history.plot(
        ax=ax,
        figsize=(16, 10),
        legend=False,
        title="Rating History",
        xlabel="Time",
        ylabel="Rating",
    )
    labelLines(ax.get_lines(), drop_label=True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(rating_history_image, dpi=150)
