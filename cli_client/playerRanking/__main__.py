import argparse
from playerRanking import playerRanking

ARGUMENT_PARSER = argparse.ArgumentParser()
ARGUMENT_PARSER.add_argument("-p", "--plot",
                             help="Plot the rating history to a file",
                             action="store_true")

if __name__ == "__main__":
    args = ARGUMENT_PARSER.parse_args()
    playerRanking.perform_evaluation(plot=args.plot)
