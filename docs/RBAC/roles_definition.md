# Role Naming Design

**Date:** 2026-04-11  
**Status:** Approved

---

## Decision

Use English slugs as technical identifiers (Clerk, code enums) and map them to Italian display labels in the frontend only.

---

## Role Definitions

| Clerk slug | UI display (IT) | Access level | Description |
|---|---|---|---|
| `project_manager` | Project Manager | Full access | Fincantieri internal — manages projects, suppliers, orders, and document checklists |
| `reviewer` | Revisore | Review access | Fincantieri internal (Ufficio Controlli Interno) — performs document due diligence alongside PM; can approve/reject documents but cannot create projects, add suppliers, or manage users |
| `approver` | Approvatore | Read-only (demo) | Fincantieri internal (Ufficio Amministrativo) — performs final check and authorises payment once client approves |
| `supplier` | Fornitore | Own data only | External supplier — views assigned orders, uploads/replaces/deletes own documents, submits when complete; no access to the internal platform |

---

## Rationale

- English slugs are unambiguous in Clerk role configuration and TypeScript enums
- "Project Manager" is standard Italian corporate terminology and needs no translation
- Italian labels (Revisore, Approvatore, Fornitore) are mapped in the frontend only, keeping the separation clean
- Supplier users are isolated to the supplier portal; internal roles (`project_manager`, `reviewer`, `approver`) are scoped to the internal portal

---

## Implementation Notes

- Clerk organisation roles should be created with the slugs above
- A single mapping object in the frontend (e.g. `ROLE_LABELS`) translates slugs to Italian for display
- The `SupplierRole` type (`"primary" | "subcontractor"`) is a sub-classification within the `supplier` role and is unaffected by this design
