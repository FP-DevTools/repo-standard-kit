Anything stated twice drifts, and the copy that drifts is the one nobody is
reading when it matters. Before writing, look for what already exists and
derive from it.

- **One home per fact.** A value, a command, a version, a path, a section
  order, a schema: declared in exactly one place, with every other use reading
  from that place
- **Derive, do not copy.** Where two artefacts must agree, generate one from
  the other or both from a shared source, and put the check that they still
  agree in the quality gates
- **Reference, do not restate.** Link to the document that owns a subject
  instead of summarising it somewhere it will go stale
- **Extend rather than parallel.** A second helper, constant, fixture, config
  key, or type that means what an existing one means is duplication even when
  the wording differs — change the original instead
- **Make unavoidable duplication fail loudly.** Where a copy cannot be removed,
  add a test or check that regenerates it and compares, so drift is a failure
  rather than a surprise
- **Deleting the stale copy is part of the change** that made it stale, not a
  follow-up

This applies to code, configuration, documentation, fixtures, and data alike.
When a change means editing the same fact in more than one file, treat that as
the defect to fix first.
