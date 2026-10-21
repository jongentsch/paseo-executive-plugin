# Worker assignment

Outcome: [the user's intended result]
Host and working directory: [selected host ID and verified host-side checkout]
Acceptance criteria: [observable behavior and required checks]
Scope: [owned files or components; exclusions; repository instructions]
Dependencies: [verified inputs, shared interface, or none]
Isolation: [existing worktree/branch and base commit, or disjoint ownership]
Provider: [user choice, when specified]

Choose an implementation that satisfies the outcome and repository conventions. Preserve unrelated work. Surface permission requests rather than bypassing them. Keep push, merge, deployment, and other external actions within the user's authorization.

Return the outcome, changed files, branch/commit and uncommitted state, actual test commands/results, evidence locations, and blockers. Identify anything not tested. Do not treat the end of the turn as proof that acceptance criteria passed.
