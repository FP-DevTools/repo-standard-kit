Agent behaviour in this repository is calibrated, not left to model defaults.
Each dial runs from 1 to 5, where 5 is the maximum:

__AGENT_DIALS__

Low verbosity means:

- Answer what was asked; do not restate the request or read the plan back
- Report outcomes, not a narration of the steps taken to reach them
- Prefer a diff, a command, or a `path:line` reference over prose describing it
- Open with the result; no preamble, and no recap the transcript already shows
- Spend words on decisions the reader must make, on risks, and on failures

High precision, repeatability, and determinism mean:

- Verify against the repository before asserting, and cite `path:line`
- Reuse the pattern already in the file rather than introducing a second one
- Make the smallest change that satisfies the requirement, and nothing beyond it
- Run the documented quality gates in order and report their real output
- Pin versions, ordering, and formatting rather than leaving them to chance
- State assumptions explicitly where the repository does not settle a choice
- The same task on the same input should reach the same result on a second run

The levels are policy values, not prose: `repo-check` reports drift from them
and `repo-adopt` restores them.
