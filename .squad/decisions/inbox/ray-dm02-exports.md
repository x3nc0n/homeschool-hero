# Ray DM-02 Export Packages

- **Context:** DM-02 needs JSON, CSV, and ZIP export packages that can represent the whole family dataset while still supporting spreadsheet-friendly review and a self-contained portability bundle.
- **Decision:** Multi-entity CSV exports are delivered as ZIP bundles containing one CSV per entity plus metadata, while ZIP exports add the full JSON snapshot, generated report/transcript/compliance PDFs, and attachment files.
- **Impact:** Families can choose a lightweight tabular export without losing per-entity structure, and the full ZIP package remains portable for future DM-01-style imports and offline archival.
