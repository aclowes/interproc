# Interproc

Tools for interacting with subprocesses beyond what is provided by
`Popen.communicate()`:
- read from stdout and stderr while the process runs
- write to stdin based on outputs from stdout or stdin

Provides:
- `interproc.run_subprocess_shell` for use with `asyncio`
- `interproc.UnixInteractiveProcess`, a replacement for `Popen`
that uses selectors.

Requirements:
- Python 3.4+