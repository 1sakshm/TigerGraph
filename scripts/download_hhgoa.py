"""Fetch the five files in the user-supplied public Google Drive dataset folder."""

import argparse
from pathlib import Path

import gdown


ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "README.md": "1-a1N26_O_wmvf2gtAuTP00jf124vbqhC",
    "case_pack.csv": "11GAxXOPWCxrB1EfePMHB9IquGJ9rDIod",
    "closed_cases_history.csv": "1S05ULujpOwSlv_YSrcDbVJcyS3JpTOZT",
    "identity.csv": "1zsMMY7lnnjZWsubsO25D9n2ZiZHSU8J_",
    "transactions.csv": "1svn7YqgPlJ-Iv3A8ar1Lh91eVWp6sukR",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/private")
    parser.add_argument("--skip-transactions", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for filename, identifier in FILES.items():
        if args.skip_transactions and filename == "transactions.csv":
            continue
        target = args.output / filename
        if target.exists() and target.stat().st_size:
            print(f"Already present: {filename} ({target.stat().st_size:,} bytes)")
            continue
        result = gdown.download(id=identifier, output=str(target), quiet=False)
        if not result or not target.exists() or target.stat().st_size == 0:
            raise RuntimeError(f"Download failed for {filename}")
        print(f"Downloaded {filename}: {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
