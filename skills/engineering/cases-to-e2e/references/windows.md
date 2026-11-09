# Running the suite on Windows

Windows PowerShell 5.1 has no `&&`, and `VAR=value cmd` does not parse. The
same commands in its own syntax:

```powershell
<pkg> -C <e2e-dir> check:types; if ($?) { <pkg> -C <e2e-dir> lint }

try {
  $env:BASE_URL = 'http://localhost:3000'
  <pkg> -C <e2e-dir> exec playwright test <spec> --project=<project>
} finally { Remove-Item Env:BASE_URL -ErrorAction SilentlyContinue }
```

- **Scope every override with `try { } finally { }`.** `$env:` lasts for the
  whole session, and dotenv never overrides an already-set variable. A leftover
  base URL sends every later run — shared-environment runs included — to
  localhost. `finally` clears it on Ctrl+C too.
- **POSIX `make` recipes need Git Bash**, called by its full path: a bare
  `bash` resolves to WSL's, a different filesystem and network. Check
  `make --version` when a recipe needs GNU-only syntax.
- **A relative `-C <dir>` resolves against the current directory**, so running
  it from inside that directory looks for `<dir>/<dir>`.
- **If Playwright reports `EPERM … playwright-transform-cache` and then
  `No tests found`**, the transform cache directory is not writable: point
  `PWTEST_CACHE_DIR` at an ignored folder for the run, inside the same
  `try { } finally { }`.
