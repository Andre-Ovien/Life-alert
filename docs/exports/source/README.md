# Editable PDF source

`build_prd.py` contains the curated client/designer copy, layout helpers and native vector diagrams. It preserves the separate detailed baseline at `docs/PRD.md`; it is not a Markdown print conversion.

To regenerate in the current Codex environment:

```sh
/Users/macbook/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 docs/exports/source/build_prd.py
```

The source uses ReportLab and embedded Liberation Sans fonts from the bundled runtime. On another machine, install ReportLab and adjust `FONT_DIR` to a directory containing LiberationSans-Regular.ttf, LiberationSans-Bold.ttf and LiberationSans-Italic.ttf. No backend dependency changes are needed.

After changing copy or layout, render every page with Poppler and inspect all pages. The builder checks text fit inside cards and enforces one-line page headings. Keep the client-facing PDF and technical baseline synchronized when requirements change.

Output: `docs/exports/Life-alert-Client-Designer-PRD-v0.2.pdf`.
Preview assets: `docs/exports/previews/01-cover.png`, `05-parallel-response.png`, and `all-pages.png`.
Verification details: `docs/exports/verification.json`.
