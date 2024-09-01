import argparse

from dotenv import load_dotenv

from player_ranking import playerRanking

ARGUMENT_PARSER = argparse.ArgumentParser()
ARGUMENT_PARSER.add_argument("-p", "--plot", help="Plot the rating history to a file", action="store_true")


def run():
    load_dotenv()
    args = ARGUMENT_PARSER.parse_args()
    playerRanking.perform_evaluation(plot=args.plot)


if __name__ == "__main__":
    run()
