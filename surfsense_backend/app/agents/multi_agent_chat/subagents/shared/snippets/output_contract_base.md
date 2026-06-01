Rules (universal):
- `status=success` -> `next_step=null`, `missing_fields=null`.
- `status=partial|blocked|error` -> `next_step` must be non-null.
- `status=blocked` due to missing required inputs -> `missing_fields` must be non-null.
- `assumptions`: any inferences you made about the user's intent; `null` when no inferences were needed.
- The `evidence` object's fields are documented in your route-specific `<output_contract>` above; never invent fields the tool did not return.
