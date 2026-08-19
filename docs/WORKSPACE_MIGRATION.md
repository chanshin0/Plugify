# Portable personal workspace migration

> Decision record — 2026-08-19: the parent container's absolute path is free on
> each device; `Plugify`, `second_brain`, and `godowon-office` remain three
> independent Git repositories; sibling placement is the default; the three
> `*_HOME` variables are used only for intentional non-sibling placement.

This document is the canonical layout and migration record for the personal
agent workspace. The workspace contains three **independent Git repositories**;
the container directory is not a fourth repository or a monorepo.

| Directory | Role | Default origin |
|---|---|---|
| `Plugify/` | Shared skills, agents, workflows, and this migration tool | `chanshin0/Plugify` |
| `second_brain/` | Personal memory | `chanshin0/second_brain` |
| `godowon-office/` | Work memory | `chanshin0/godowon-office` |

The container may have any absolute path on macOS, Linux, or Windows/WSL.
Additional non-repository directories are allowed. The invariant is only that
the three repositories above are siblings by default.

## Path resolution contract

Every shared instruction that needs another repository resolves it in this
order:

1. Use the repository-specific environment variable when it is explicitly set:
   `PLUGIFY_HOME`, `SECOND_BRAIN_HOME`, or `GODOWON_OFFICE_HOME`.
2. Otherwise, use the named repository under the current consumer repository's
   workspace parent (the sibling layout).
3. Validate that the result is the expected Git checkout and remote. If it is
   missing or wrong, fail with a clear error. Never guess a home directory or
   silently fall back to an old clone.

Here, the consumer anchor is the repository that owns the resolving code or
instruction, not whichever product happens to be the shell cwd. Globally
installed Plugify skills therefore resolve from their active, source-linked
Plugify checkout and its parent.

Sibling layout needs no environment variables. Set the variables only for an
intentional non-sibling layout, using absolute paths. Plugify's migration CLI
uses its own checkout as the consumer anchor and exposes that resolver for
scripts and diagnostics:

```bash
cd "/absolute/path/to/Plugify"
python3 scripts/workspace-migrate.py --resolve second_brain
python3 scripts/workspace-migrate.py --resolve godowon-office
```

Replace `/absolute/path/to/Plugify` with the checkout's actual path. Set `PLUGIFY_HOME`
only when that checkout intentionally is not a sibling of the other repositories.

## Bootstrap a new device

Prerequisites are Git, Python 3, Bash, and access to the three private GitHub
repositories. SSH origins additionally require OpenSSH. During clone the tool
disables Git/SSH askpass, Git Credential Manager interaction, and terminal
credential prompts. SSH is forced to `BatchMode=yes` and strict existing
host-key trust; inherited askpass or `GIT_SSH_COMMAND` overrides are not used.
Configure and test the SSH key, agent/passphrase handling, and host key on the
device first. Missing credentials or trust then fail instead of opening a hidden
prompt. Choose a local container, clone Plugify first, inspect the dry-run, then
apply:

```bash
workspace_root="$HOME/Work"
mkdir -p "$workspace_root"
git clone git@github.com:chanshin0/Plugify.git "$workspace_root/Plugify"
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root"
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root" --apply --install
```

The apply step clones only missing repositories. It validates existing origins,
sets repository-local `core.autocrlf=false` and `core.eol=lf`, creates a managed
root `AGENTS.md`, and writes `.plugify-workspace.json`. `--install` is separate
and explicit because it updates the current user's Claude/Codex integration.
Restart those applications after installation so their registries reload.

In Codex desktop, perform one local step per device: open/save the **container
folder** as the workspace/session root, rather than opening one child as the
root. The generated root `AGENTS.md` then acts as the session-start router and
explicitly tells the agent to read the selected child's rules before acting.
Codex discovers `AGENTS.md` once from the project root down to the starting
directory, so changing directories later does not replace that explicit read.
This follows Codex's official
[AGENTS.md discovery and precedence](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
contract. Opening a child directly is still valid for a child-only task; Codex
then discovers that Git root's `AGENTS.md`, but not the container router.

If `godowon-office` has a previously registered reservation or scheduled
service on this device, Git migration does not rewrite its embedded checkout
path. While the old checkout still exists, inspect status there, disable and
uninstall the owned service with that old checkout's installer, and only then
run install, preflight, and an explicit enable from the new checkout according
to that repository's README/operations instructions. A new checkout correctly
refuses to overwrite an installation owned by a different root. If the old
checkout is already gone, stop: do not delete unit files by hand. Require
explicit user-authorized manual recovery after the installed units and ownership
manifest have been inspected. Workspace migration itself never starts, removes,
or reinstalls a scheduled service.

HTTPS and SSH GitHub origins for the same owner/repository are treated as the
same identity when they use their transport's default port. A non-default port
is part of the identity. Approved mirrors can be declared with repeatable
`--repo-url NAME=URL`, but the same overrides must be supplied for later strict
verification. The managed local manifest records those approved identities, so
`--resolve` also works in a mirror-backed workspace. A resolver trusts that file
only when its schema, manager, layout, exact repository fields, and
credential-free origins all validate.

## Migrate an existing device

1. In every existing clone, inspect `git status` and make sure work that matters
   is committed and pushed. Meeting/audio originals and other repository policy
   boundaries still apply.
2. Pick the target container. Place clean existing checkouts at the three exact
   sibling names, or let the tool clone fresh copies. The tool intentionally does
   not move, pull, reset, delete, or overwrite a checkout.
3. Run the dry-run. Resolve every wrong-origin, occupied-path, dirty-tree, or
   un-managed root `AGENTS.md` error before applying.
4. Run `--apply`, then strict verification. Use `--allow-dirty` only when you have
   deliberately reviewed a dirty checkout; the tool will leave its working tree
   untouched.

```bash
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root"
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root" --apply
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root" --verify
```

The migration tool never updates an existing branch. When updates are wanted,
run `git pull --ff-only` separately inside each clean repository so that a branch
or authentication problem cannot be confused with workspace migration.

## Safety and idempotence

- Default execution is a read-only dry-run; writes require `--apply`.
- All existing repository paths are validated before any clone or local config
  change. Fetch origins, every effective push URL, and dirty trees fail closed
  by default; dirty filenames are not copied into logs.
- The container must be outside any existing Git worktree, Git metadata
  directory, or bare repository. Inherited Git-dir/worktree/index routing is
  removed from every Git subprocess, advanced config/exec/template/trace
  environment selectors are ignored, clone uses a controlled empty Git
  template, and diagnostic calls disable optional index refresh locks.
- Each required repository must be a physical child directory rather than a
  symlink. A differently-cased collision with a required name is rejected so a
  layout created on Linux can still round-trip to default macOS/Windows filesystems.
- Missing repositories are cloned to unique temporary directories and renamed
  into place only after every clone validates.
- A custom root `AGENTS.md` is never overwritten. Only a file bearing the exact
  Plugify managed marker can be updated automatically.
- The local manifest and router contain the contract, not personal/work content.
- Repeating apply produces the same router, manifest, and local Git settings.

## Shared Git versus machine-local state

| Shared and portable | Machine-local and intentionally not committed |
|---|---|
| This document, migration tool, and router template | Container absolute path |
| Repository names, roles, and default origins | `.plugify-workspace.json` generated at the container root |
| Environment variable names and sibling fallback | Claude/Codex config, caches, credentials, and hook trust |
| Each repository's own policy | Compatibility symlinks and local validation artifacts |

Absolute device paths belong only in local config. Shared instructions must use
the resolution contract, so a desktop, laptop, and Mac may choose different
container paths without forcing the same path on the other devices.

## Product-branch scan is separate

`scripts/status.sh`, `scripts/heartbeat.sh`, and telemetry can optionally scan
product repositories that contain `.planning/STATE.md`. Those products are not
members of this three-repository personal workspace. Their scan root is an
explicit first argument or `PLUGIFY_PROJECTS_DIR`, with `$HOME/Projects` retained
only as a backward-compatible local default.

## Verification and rollback

Strict verification checks the three origins, clean state unless explicitly
allowed, root router, local manifest, and EOL settings:

```bash
python3 "$workspace_root/Plugify/scripts/workspace-migrate.py" --root "$workspace_root" --verify
```

There is no destructive automatic rollback. A failed dry-run changes nothing. A
failed clone removes its own temporary directory. If apply completed and you
choose to undo it, first inspect `.plugify-workspace.json` and `git status` in
each repository; remove only newly cloned clean checkouts and managed root files
that you have independently confirmed are disposable. Reverse Plugify's user
integration separately and only for symlinks/hooks that still point at this
checkout. This deliberate manual boundary prevents a rollback from deleting
pre-existing work.
