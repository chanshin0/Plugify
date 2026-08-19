<!-- plugify-workspace-router:v1 -->
# Personal Workspace Router

This directory is a container for independent Git repositories. It is not a
monorepo and must not be initialized as a Git repository itself.

## Repository routing

- Shared agent processes, skills, and migration tooling: `Plugify/`
- Personal thoughts, preferences, and life decisions: `second_brain/`
- Work facts, meetings, tasks, people, and projects: `godowon-office/`

Before reading or writing a child repository, enter that repository and read
its own `AGENTS.md` and `POLICY.md` when present. Run Git commands inside the
selected child only. Never mix personal and work memory.

Both brain repositories are private. In an unrelated session, do not scan or
bulk-inject their bodies. For `godowon-office`, read its policy first and use
only its bounded retrieval command for the current work-memory question. For
`second_brain`, follow its policy and retrieve only the personal context needed
for the task.

A container-root or cross-repository session is not confidently personal and
must not be auto-distilled into `second_brain`. Capture a personal thought from
such a session only through that repository's explicit `bin/idea` workflow.

## Portable path contract

The normal layout is the three sibling directories above, regardless of this
container's absolute path. Code or instructions in one child resolve another
named repository under the current child's workspace parent. A
repository-specific environment override takes precedence only when a
non-sibling layout is intentional:

- `PLUGIFY_HOME`
- `SECOND_BRAIN_HOME`
- `GODOWON_OFFICE_HOME`

An override must be an absolute path to the expected Git checkout. If neither
a valid override nor the expected sibling exists, stop and report the missing
repository; do not guess another path.

Machine-local configuration, compatibility symlinks, caches, and generated
artifacts may live beside these repositories, but their absolute paths must not
be copied into shared Git instructions.
