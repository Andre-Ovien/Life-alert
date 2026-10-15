# Editable designer handoff source

Run with the bundled Python runtime (ReportLab required for PDF only):

```sh
python3 docs/exports/source/screen-handoff/build_inventory.py
python3 docs/exports/source/screen-handoff/build_state_checklist.py
python3 docs/exports/source/screen-handoff/build_pdf.py
```

`build_inventory.py` holds all 65 screen definitions and produces `screens.json` plus `docs/DESIGNER-HANDOFF.md`. `states.json` contains the exhaustive required state names. `build_state_checklist.py` creates the simple `SCREEN-LIST.md`, CSV state checklist and machine-checked totals. `build_pdf.py` creates the designed 18-page PDF using embedded fonts and native vector diagrams; it borrows the visual language of the earlier PRD without changing it.

The PDF builder currently uses Liberation Sans fonts at the Codex bundled runtime path. On another machine, point FONT_DIR to an equivalent installed Liberation Sans family. No backend requirements are changed. Re-render and inspect every page after substantive layout edits.

These documents contain the complete current baseline with no pricing or proposed scope cuts. Production/provider decisions can change future workflows and require versioned review. Flutter screen IDs match the current consumer route catalog; if inventory routes change, update that catalog and tests deliberately rather than generating empty screen files.
