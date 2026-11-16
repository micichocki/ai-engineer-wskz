"""Routing benchmark against the live stack: `python batch.py <label> [api-url]`.

Sends every message from bench/messages.csv once and writes bench/results/<label>.json.
"""

import csv
import json
import sys
import time
from pathlib import Path

import httpx

BENCH = Path(__file__).parent / "bench"
label = sys.argv[1]
api = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

rows = []
with (BENCH / "messages.csv").open(encoding="utf-8") as f, httpx.Client(timeout=300) as http:
    for case in csv.DictReader(f):
        body = {"email": "batch@example.com", "message": case["message"]}
        start = time.monotonic()
        r = http.post(f"{api}/api/v1/messages", json=body)
        seconds = round(time.monotonic() - start, 2)
        # An error (503: no usable model answer) counts as a miss, with got = the status code.
        got = r.json()["recipient"].split("@")[0] if r.status_code == 200 else str(r.status_code)
        rows.append({**case, "got": got, "seconds": seconds})
        mark = "ok" if got == case["expected"] else "WRONG"
        print(
            f"{mark:5} {seconds:5.1f}s {case['message'][:55]:55} "
            f"want {case['expected']:15} got {got}",
            flush=True,
        )

(BENCH / "results").mkdir(exist_ok=True)
(BENCH / "results" / f"{label}.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
)
for name in ("seen", "fresh"):
    part = [row for row in rows if row["set"] == name]
    print(f"{name}: {sum(row['got'] == row['expected'] for row in part)} of {len(part)} correct")
print(f"median {sorted(row['seconds'] for row in rows)[len(rows) // 2]} s")
