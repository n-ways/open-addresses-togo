#!/usr/bin/env python3
"""Join every footprint to its area and density and sort by area, for grouping one area at a time.

  python3 tools/sort-buildings.py <work folder>

Reads <work>/buildings-raw.csv (tools/extract-buildings.py) and <work>/area-of.csv
(tools/assign-areas.py); writes <work>/buildings.csv sorted by area, then position, so
the order never depends on the extract's (DuckDB, memory_limit 3GB).
"""
import os, subprocess, sys

work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false; SET temp_directory='{W('duck-tmp')}';
COPY (SELECT a.aid, a.dens, b.* EXCLUDE (bid)
      FROM read_csv('{W('buildings-raw.csv')}', header=true, all_varchar=true, max_line_size=16000000) b
      JOIN read_csv('{W('area-of.csv')}', header=true, all_varchar=true) a USING (bid)
      ORDER BY a.aid, CAST(b.lat AS DOUBLE), CAST(b.lon AS DOUBLE), CAST(b.area AS DOUBLE), b.src, b.oid)
  TO '{W('buildings.csv')}' (HEADER, DELIMITER ',');
"""
r = subprocess.run(['duckdb'], input=sql, capture_output=True, text=True)
print(r.stdout[-1000:], r.stderr[-2000:])
sys.exit(r.returncode)
