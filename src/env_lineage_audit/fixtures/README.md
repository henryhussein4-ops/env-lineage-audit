# Fixtures

This directory holds the live views of the harness environment used by the
`live` sample. Both are symlinks, not copies:

- `runner_envelope` → `/home/runner/work/_temp/_runner_file_commands` —
  the GitHub Actions command-file directory for the current job. The
  `set_env_*` files in it are the `$GITHUB_ENV` records that earlier workflow
  steps exported, one `KEY=VALUE` per line.
- `runner_environ.txt` → `/proc/self/environ` — the same environment in
  POSIX `environ` form (NUL-separated).

Reading either fixture therefore yields the environment of the job that is
reading it, which is what makes the `live` manifest live.
