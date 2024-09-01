import argparse

from cli_client.clanmanager import playerRanking
from dotenv import load_dotenv

ARGUMENT_PARSER = argparse.ArgumentParser()
ARGUMENT_PARSER.add_argument(
    "-p", "--plot", help="Plot the rating history to a file", action="store_true"
)

def main():
    load_dotenv()
    args = ARGUMENT_PARSER.parse_args()
    playerRanking.perform_evaluation(plot=args.plot)

if __name__ == "__main__":
    main()
