# Frontend

This app is a presentation layer for the parsed marathon plan JSON.

## What It Does

- renders the 18-week plan as a selectable schedule and workout explorer
- exposes a separate pace configuration panel
- projects configured paces into workout cards and segment summaries
- keeps the parser output as source data instead of duplicating plan logic in the UI

## Data Source

The app imports:

- [`../output/parsed_training_plan.uk.pretty.json`](/Users/inceon/Develop/nike-training-plan/output/parsed_training_plan.uk.pretty.json)

That means the normal workflow is:

1. parse the PDF
2. regenerate the Ukrainian JSON
3. regenerate week preview images
4. open the frontend

The preview images are rendered from the original PDF with:

```bash
python ../scripts/render_week_previews.py
```

## Commands

```bash
npm install
npm run dev
npm run build
```
