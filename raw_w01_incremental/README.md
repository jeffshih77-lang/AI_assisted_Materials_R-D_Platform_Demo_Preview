# RAW-W01 TWSE_DAILY_K incremental correction (2026-09-07..2026-09-17)

Scope is deliberately narrow: nine candidate TWSE trading dates after the existing 2026-09-04 boundary.

Authority and RAW semantics are inherited from frozen RAW-W01:
- official TWSE `MI_INDEX`, `type=ALLBUT0999`, `response=json`;
- store `gzip(exact HTTP response bytes)`;
- SHA-256 is over the uncompressed exact response bytes;
- requested date must exactly equal payload date;
- no reconstruction, no zero-fill, no current/latest fallback, no Canonical transformation.

Governance sidecars preserve package/member SHA, source URL, requested/source date, retrieval timestamp, and raw-layer PIT lineage. `available_at` remains explicitly unknown at RAW layer and must not be guessed.

The GitHub Actions artifact is transport only. Formal cloud admission requires uploading the inner official RAW package as a new immutable object, uploading manifest/receipt/coverage evidence, and verifying Drive readback bytes/SHA before marking `CLOUD_VERIFIED`.
