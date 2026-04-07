from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from parser.translate_uk import translate_output_file, translate_output_file_pretty


def main() -> None:
    source_compact = REPO_ROOT / "output" / "parsed_training_plan.json"
    source_pretty = REPO_ROOT / "output" / "parsed_training_plan.pretty.json"
    target_compact = REPO_ROOT / "output" / "parsed_training_plan.uk.json"
    target_pretty = REPO_ROOT / "output" / "parsed_training_plan.uk.pretty.json"

    translate_output_file(source_compact, target_compact)
    translate_output_file_pretty(source_pretty, target_pretty)

    print(f"Wrote {target_compact}")
    print(f"Wrote {target_pretty}")


if __name__ == "__main__":
    main()
