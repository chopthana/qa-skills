# Flow mechanics that have already bitten

Each of these cost somebody a debugging session. Respect them before you
theorize about a failure.

- **Processing flows are slow.** Playwright's default timeout is 30–60s.
  Upload → process → result flows need an explicit `test.setTimeout(...)` and
  long waits on the result navigation — reached by URL, not by a heading whose
  accessible name swallows adjacent icons.
- **Wait on signals, not clocks.** `page.waitForResponse()`, `waitForURL`, a
  wait-for-API helper. The only sanctioned sleeps serve the human watching the
  video: the holds inside the marked-click and capture helpers (§4). Never
  sleep as a substitute for a signal.
- **The app can silently no-op.** Handlers that return early when nothing
  changed (a save that presents no confirm modal when no field was touched)
  will hang a fixture that unconditionally waits for the confirmation. The
  fixture branches on "did anything actually change".
- **Default sorts bury old rows pages deep.** A record from months ago is
  unreachable by paging a hundred-row history — navigate with the route's own
  query params instead.

  > **Worked example** — one history screen validates `?mode=month&period=YYYY-MM`
  > in its route schema, so the spec jumps straight to the month it needs.
- **Design systems can render duplicate accessibility nodes** (a disabled
  shadow checkbox beside the real one) — strict mode then double-matches. Scope
  by element + role or `.first()`, and confirm against the page snapshot from
  an actual failure (Playwright's `error-context.md`) rather than theorizing.
- **Reruns persist.** Upload and process write real records on a shared
  environment; sequence numbers advance every rerun. Assert by shape (a regex),
  never a hardcoded sequence. For filenames carrying a timestamp, validate
  against the click window in the app's own timezone, with about a minute of
  tolerance.
- **Warning dialogs are conditional.** A rerun hits a "this file was already
  uploaded" dialog where a first run does not. Handle both with a `.or()` race
  and then branch on `isVisible()`.
- **Missing assets skip, not fail.** `test.skip(!fs.existsSync(...))` at the
  **top of the test**, not inside a step — a mid-test skip abandons a run that
  has already captured evidence. A green run may legitimately contain skips;
  say so in your report.
- **Reach preconditions without writing to the shared environment.** "A
  processed run exists" does not mean "run upload and process first" — find an
  existing one through the read-only history or report page, and `test.skip`
  with a named reason when the environment has none.
- **A `webServer` timeout is not a spec failure.** When Playwright times out
  booting, the configured base URL was unreachable (network/VPN down,
  environment asleep). Probe reachability before rerunning, and print only the
  status — never echo the URL or any credential.
- **A local-only suite needs the local URL explicitly.** The default env file
  may point the base URL at the shared environment, in which case a spec gated
  on localhost skips silently while an ungated sibling writes its run to the
  shared one. Override per run, not in the file — dotenv never overrides an
  already-set variable, so a one-off `BASE_URL=... <test command>` is enough.
- **A generic server error is environment until proven otherwise.** An
  unspecific "something went wrong" page hides its cause, and an identical
  rerun fails identically. Read the service's own logs before rerunning.

  > **Worked example** — one stack runs its data warehouse as a Docker
  > emulator, so the team reads
  > `docker logs "$WAREHOUSE_CONTAINER" --since 10m | grep ERROR` and has seen
  > two causes there: a "table not found" on an empty project id (one env var
  > unset) seconds after upload, and a 20-second dial timeout to an internal
  > service (off the network). Find your stack's equivalent log; the container
  > name is yours to supply, never a default.
