"""CLI entry point for tishcode."""

import argparse

from dotenv import load_dotenv

from src.handlers import handle_fixissue, handle_fixpr, handle_review
from src.logger import setup_logger


def main() -> None:
    load_dotenv()
    setup_logger()

    parser = argparse.ArgumentParser(description="tishcode - AI coding agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixissue_parser = subparsers.add_parser("fixissue", help="Process GitHub issue")
    fixissue_parser.add_argument("issue_url", help="GitHub issue URL")

    review_parser = subparsers.add_parser("review", help="Review pull request")
    review_parser.add_argument("pr_url", help="GitHub pull request URL")

    fixpr_parser = subparsers.add_parser("fixpr", help="Fix pull request")
    fixpr_parser.add_argument("pr_url", help="GitHub pull request URL")

    args = parser.parse_args()

    if args.command == "fixissue":
        handle_fixissue(args.issue_url)
    elif args.command == "review":
        handle_review(args.pr_url)
    elif args.command == "fixpr":
        handle_fixpr(args.pr_url)


if __name__ == "__main__":
    main()
