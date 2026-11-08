# Lab dashboard: API requests for the backend

The dashboard (`lab/`) works around every item below today. None of them is blocking; they
would remove the workarounds noted.

1. **SSE replay after a re-analysis** (`GET /lab/api/evidence/{id}/events`).
   The stream replays every stored event from index 0 and returns at the *first* `done` event.
   After `POST /evidence/{id}/reanalyze` the in-memory list still holds the previous run, so a
   new connection replays the old run and closes at its `done` before the new run's events.
   *Workaround:* the UI detects "stream finished but the record is still queued/analyzing" and
   polls `GET /evidence/{id}` (whose `events` holds every run; the UI keeps the events after the
   last `queue` stage). *Request:* support `?since=<n>` / `Last-Event-ID`, or start the replay at
   the last `queue` event.

2. **One stream per case.** Browsers allow ~6 HTTP/1.1 connections per host, so the case grid
   streams at most 3 pending exhibits at once and polls `GET /cases/{id}` for the rest.
   *Request:* `GET /lab/api/cases/{id}/events` multiplexing the progress events of all exhibits.

3. **Verdict counts in `GET /lab/api/cases`.** Case cards on the home screen need the per-verdict
   distribution, so the UI calls `GET /cases/{id}` once per case. *Request:* include `counts`
   (or the new `findings.counts`) in each `/cases` row.

4. **Execution order in `GET /lab/api/techniques`.** It returns `catalogue.ALL` order, but the
   engine runs `for_kind()` sorted by `(order, id)`, so the "waiting" rows of the live checklist
   are in a slightly different order from the real run. *Request:* add the `order` field.

5. **Demo availability.** `POST /lab/api/demo` currently returns 500 (module
   `satyapan.forensics.demo` missing) and the only way to learn whether a demo dataset exists is
   to POST (which resets the demo case). The UI disables the button after a 404/500.
   *Request:* `GET /lab/api/demo` → `{available: bool}` (or a `demo_available` flag in `/health`).

6. **Observation, not a UI issue:** on this workstation several MP4 exhibits report
   `could not analyse: no decodable audio stream (... Error opening output files: Invalid
   argument)` for the audio techniques, although `media.has_audio` is true and the files play
   with sound in the browser. Possibly the ffmpeg invocation used to extract audio.
