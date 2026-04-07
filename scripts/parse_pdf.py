from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parser import parse_training_pdf
from parser.utils import ensure_directory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse a Nike marathon training PDF into normalized JSON.")
    parser.add_argument("pdf_path", help="Path to the source PDF file.")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for parsed JSON outputs. Defaults to ./output",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    ensure_directory(output_dir)

    document = parse_training_pdf(args.pdf_path)
    compact_path = output_dir / "parsed_training_plan.json"
    pretty_path = output_dir / "parsed_training_plan.pretty.json"

    compact_path.write_text(document.model_dump_json(by_alias=False), encoding="utf-8")
    pretty_path.write_text(document.model_dump_json(indent=2, by_alias=False), encoding="utf-8")

    print(f"Wrote {compact_path}")
    print(f"Wrote {pretty_path}")


if __name__ == "__main__":
    main()
