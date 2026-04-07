from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import fitz


def main() -> None:
    pdf_path = REPO_ROOT / "docs" / "nike-run-club-marathon-ru_RU.pdf"
    parsed_path = REPO_ROOT / "output" / "parsed_training_plan.pretty.json"
    output_dir = REPO_ROOT / "frontend" / "public" / "week-previews"
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
    weeks = parsed["weeks"]
    document = fitz.open(str(pdf_path))

    for week in weeks:
        week_number = week["week_number"]
        page_number = week["source_pages"][0]
        page = document[page_number - 1]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), alpha=False)
        filename = f"week-{week_number:02d}-page-{page_number}.png"
        target = output_dir / filename
        pixmap.save(target)
        print(f"Rendered {target}")


if __name__ == "__main__":
    main()
