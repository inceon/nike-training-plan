# Nike Marathon PDF Parser

## Design

The parser is layout-aware and rule-based.

- `PyMuPDF` (`fitz`) is the primary extraction engine for page text, blocks, clipped regions, and page classification.
- `pdfplumber` is used only for the pace table because its table extraction is more reliable than rebuilding the grid manually.
- OCR is intentionally not the default because this PDF is text-based. OCR would throw away clean text geometry, lower accuracy for pace/workout tokens, and make maintenance harder.

## Pipeline

1. Load the PDF and snapshot every page with raw text, ordered text blocks, and a page type.
2. Classify pages into intro/reference, pace table, glossary, advice, weekly plan, schedule, and closing pages.
3. Parse weekly pages with fixed layout regions:
   - header
   - center workout column
   - left recovery column
   - right recovery column
4. Normalize times, paces, distances, repeats, and recovery durations into machine-friendly values.
5. Validate the final document model and fail on structural inconsistencies.
6. Write compact and pretty JSON outputs.

## Why The Schema Fits Future Plan Generation

The schema separates three concerns:

- canonical meaning: `workout_type`, `subtype`, `target_pace_type`
- normalized prescription data: segment distances, durations, reps, recovery, target ranges
- raw traceability: source pages and raw snippets

That separation makes it practical to:

- swap workouts by subtype
- scale long-run or recovery volume
- remap plans onto calendar days
- attach pace profiles later
- export workouts into app-specific builders without reparsing the PDF

## Extension Points

- Add new page classifiers in [`parser/extract.py`](/Users/inceon/Develop/nike-training-plan/parser/extract.py).
- Adjust Nike-style week layout regions and section splitting in [`parser/parse_weeks.py`](/Users/inceon/Develop/nike-training-plan/parser/parse_weeks.py).
- Extend normalization patterns for new pace or distance phrasing in [`parser/utils.py`](/Users/inceon/Develop/nike-training-plan/parser/utils.py).
- Add alternate table strategies in [`parser/parse_pace_table.py`](/Users/inceon/Develop/nike-training-plan/parser/parse_pace_table.py).

## Usage

```bash
python scripts/parse_pdf.py docs/nike-run-club-marathon-ru_RU.pdf
```

Outputs:

- [`output/parsed_training_plan.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.json)
- [`output/parsed_training_plan.pretty.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.pretty.json)
- [`output/parsed_training_plan.uk.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.uk.json)
- [`output/parsed_training_plan.uk.pretty.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.uk.pretty.json)

Translation is a separate post-processing step, not part of PDF parsing:

```bash
python scripts/translate_output_to_uk.py
```

PDF page previews for the 18 weekly pages are also generated as a separate step:

```bash
python scripts/render_week_previews.py
```

## Frontend

A standalone React app lives in [`frontend/`](/Users/inceon/Develop/nike-training-plan/frontend).

- It presents the parsed training plan as an interactive schedule and week explorer.
- It keeps pace configuration separate from the parser output, so user-specific pace profiles can be layered onto the same normalized JSON model.
- It reads the Ukrainian parser output directly from [`output/parsed_training_plan.uk.pretty.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.uk.pretty.json).
- It shows the corresponding rendered PDF page preview for the selected week from [`frontend/public/week-previews/`](/Users/inceon/Develop/nike-training-plan/frontend/public/week-previews).

Run it with:

```bash
cd frontend
npm install
npm run dev
```

Build it with:

```bash
cd frontend
npm run build
```

## Vercel

This repo is configured for Vercel with [`vercel.json`](/Users/inceon/Develop/nike-training-plan/vercel.json).

Important:

- Connect the repository root to Vercel, not just [`frontend/`](/Users/inceon/Develop/nike-training-plan/frontend).
- The frontend imports parsed JSON from [`output/`](/Users/inceon/Develop/nike-training-plan/output), so using `frontend` as the Vercel root directory can break those imports.

Deploy flow:

1. Push the repo to GitHub/GitLab/Bitbucket.
2. Import the repository in Vercel.
3. Leave the project root as the repository root.
4. Vercel will use:
   - `installCommand`: `cd frontend && npm install`
   - `buildCommand`: `cd frontend && npm run build`
   - `outputDirectory`: `frontend/dist`

Before deploying, make sure these generated assets already exist in the repo:

- [`output/parsed_training_plan.uk.pretty.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.uk.pretty.json)
- [`frontend/public/week-previews/`](/Users/inceon/Develop/nike-training-plan/frontend/public/week-previews)
