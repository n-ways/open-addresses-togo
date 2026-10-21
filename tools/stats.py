#!/usr/bin/env python3
"""Design statistics for Togo: buildings per unit and the Grand Lomé sample (model/stats/).

  NWAYS_ROOT=<data folder> python3 tools/stats.py <work> keys.geojson KEYFIELD capital.geojson OUTDIR [rural]

<work> holds the context exports of the design (<work>/adm/togo-ctx.geojsonseq: walls, gates, landuse;
<work>/st/places-TG.csv: places), and receives DuckDB's spill files.

Pass A: buildings per key polygon (OSM + ML), for code lengths.
Pass B: inside the capital polygon(s): building profile inputs (class
evidence, size, height), walls/gates, neighbour pairs for compound grouping;
then compound grouping and summary statistics in Python.
"""
import csv, io, json, math, os, subprocess, sys, collections

ROOT = os.environ.get('NWAYS_ROOT') or sys.exit('set NWAYS_ROOT to the folder holding the map data (tools/README.md)')
cc, slug = 'TG', 'togo'
SCR, keys, keyfield, capital, out = (os.path.abspath(sys.argv[1]),) + tuple(sys.argv[2:6])
os.makedirs(out, exist_ok=True)
osm = f'{ROOT}/data/detail/countries/{slug}/buildings-src.geojsonseq'
ml = f'{ROOT}/data/detail/ml/{cc}.parquet'
ctx = f'{SCR}/adm/{slug}-ctx.geojsonseq'
places = f'{SCR}/st/places-{cc}.csv'
TMP = f'{SCR}/duck-tmp'
os.makedirs(TMP, exist_ok=True)

HEAD = f"""SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;
SET temp_directory='{TMP}'; LOAD spatial;"""
LINES = lambda p: (f"read_csv('{p}', columns={{'line': 'VARCHAR'}}, header=false, delim=chr(1), quote='', escape='', "
                   f"max_line_size=16000000)")


def duck(sql):
    r = subprocess.run(['duckdb', '-csv'], input=HEAD + sql, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(r.stderr[-3000:])
    return r.stdout


def J(path):
    return f"json_extract_string(j, '$.properties.\"{path}\"')"


osm_sel = f"""SELECT 'osm' AS src, ST_GeomFromGeoJSON(json_extract(j, '$.geometry')) AS g,
  {J('building')} AS btag, {J('building:levels')} AS levels, {J('height')} AS height,
  ({J('name')} IS NOT NULL)::int AS named, coalesce({J('amenity')}, {J('shop')}, {J('office')}, {J('tourism')}, {J('healthcare')}) AS poi
  FROM (SELECT ltrim(line, chr(30)) AS j FROM {LINES(osm)} WHERE length(line) > 2)"""
ml_sel = f"SELECT 'ml' AS src, geometry AS g, NULL AS btag, NULL AS levels, CAST(h AS VARCHAR) AS height, 0 AS named, NULL AS poi FROM '{ml}'"

# ---------- Pass A: per key ----------
if not os.path.exists(f'{out}/per-key.csv'):
    sql = f"""
    CREATE TABLE k AS SELECT "{keyfield}" AS key, geom FROM ST_Read('{keys}');
    CREATE TABLE b AS SELECT src, ST_Centroid(g) AS c, ST_Area(g) * 110574.0 * 111320.0 * cos(radians(ST_Y(ST_Centroid(g)))) AS a
      FROM ({osm_sel} UNION ALL {ml_sel});
    COPY (SELECT k.key, count(*) FILTER (WHERE src='osm') AS osm, count(*) FILTER (WHERE src='ml') AS ml,
           count(*) AS total, round(median(a),1) AS median_m2, count(*) FILTER (WHERE a < 25) AS small_lt25
          FROM b JOIN k ON ST_Contains(k.geom, b.c) GROUP BY k.key ORDER BY total DESC) TO '{out}/per-key.csv' (HEADER);
    """
    duck(sql)
    print('pass A done', flush=True)

# ---------- Pass B: capital ----------
sql = f"""
CREATE TABLE cap AS SELECT ST_Union_Agg(geom) AS g FROM ST_Read('{capital}');
CREATE TABLE bx AS SELECT ST_XMin(g) x0, ST_YMin(g) y0, ST_XMax(g) x1, ST_YMax(g) y1 FROM cap;
CREATE TABLE raw AS SELECT * FROM ({osm_sel} UNION ALL {ml_sel}) r, bx
  WHERE ST_XMin(r.g) >= bx.x0 AND ST_XMax(r.g) <= bx.x1 AND ST_YMin(r.g) >= bx.y0 AND ST_YMax(r.g) <= bx.y1;
CREATE TABLE b AS SELECT row_number() OVER () AS id, src, g, btag, levels, height, named, poi,
   ST_X(ST_Centroid(g)) AS cx, ST_Y(ST_Centroid(g)) AS cy,
   ST_Area_Spheroid(ST_FlipCoordinates(g)) AS area, ST_Perimeter_Spheroid(ST_FlipCoordinates(g)) AS perim
  FROM raw WHERE ST_Contains((SELECT g FROM cap), ST_Centroid(g));
CREATE TABLE ctx AS SELECT json_extract_string(j,'$.properties.barrier') AS barrier, json_extract_string(j,'$.properties.landuse') AS landuse,
   ST_GeomFromGeoJSON(json_extract(j,'$.geometry')) AS g
  FROM (SELECT ltrim(line, chr(30)) AS j FROM {LINES(ctx)} WHERE length(line) > 2);
CREATE TABLE ctxc AS SELECT * FROM ctx, bx WHERE ST_Intersects(ctx.g, ST_MakeEnvelope(bx.x0, bx.y0, bx.x1, bx.y1));
CREATE TABLE encl AS SELECT row_number() OVER () AS eid, poly AS g, ST_Area_Spheroid(ST_FlipCoordinates(poly)) AS ea FROM (
   SELECT CASE WHEN ST_GeometryType(g)='LINESTRING' AND ST_IsClosed(g) AND ST_NPoints(g) >= 4 THEN ST_MakePolygon(g)
               WHEN ST_GeometryType(g) IN ('POLYGON','MULTIPOLYGON') THEN g END AS poly
   FROM ctxc WHERE barrier IN ('wall','fence','hedge')) WHERE poly IS NOT NULL;
CREATE TABLE lu AS SELECT landuse, g FROM ctxc WHERE landuse IS NOT NULL AND ST_GeometryType(g) IN ('POLYGON','MULTIPOLYGON');
CREATE TABLE pl AS SELECT id AS pid, category, source, ST_Point(st_x, st_y) AS p FROM read_csv('{places}', header=true, quote='"', escape='"') p, bx
   WHERE st_x BETWEEN bx.x0 AND bx.x1 AND st_y BETWEEN bx.y0 AND bx.y1;
CREATE TABLE bpoi AS SELECT b.id, string_agg(DISTINCT pl.category, '|') AS cats FROM b JOIN pl ON ST_Contains(b.g, pl.p) GROUP BY b.id;
CREATE TABLE benc AS SELECT id, arg_min(eid, ea) AS eid, min(ea) AS ea FROM (SELECT b.id, e.eid, e.ea FROM b JOIN encl e ON ST_Contains(e.g, ST_Point(b.cx, b.cy))) GROUP BY id;
CREATE TABLE blu AS SELECT id, any_value(landuse) AS landuse FROM (SELECT b.id, lu.landuse FROM b JOIN lu ON ST_Contains(lu.g, ST_Point(b.cx, b.cy))) GROUP BY id;
COPY (SELECT b.id, src, round(cx,7) cx, round(cy,7) cy, round(area,1) area, round(perim,1) perim, btag, levels, height, named, poi,
        bpoi.cats, benc.eid, round(benc.ea,0) ea, blu.landuse
      FROM b LEFT JOIN bpoi USING (id) LEFT JOIN benc USING (id) LEFT JOIN blu USING (id)) TO '{out}/cap-buildings.csv' (HEADER);
COPY (SELECT a.id AS a, b2.id AS b, round(ST_Distance_Spheroid(ST_FlipCoordinates(ST_Centroid(a.g)), ST_FlipCoordinates(ST_Centroid(b2.g))),1) AS dc,
        round(ST_Distance(a.g, b2.g) * 110900, 2) AS gap
      FROM b a JOIN b b2 ON ST_DWithin(a.g, b2.g, 0.00011) AND a.id < b2.id) TO '{out}/cap-pairs.csv' (HEADER);
COPY (SELECT count(*) FILTER (WHERE barrier IN ('gate','lift_gate','swing_gate','sliding_gate')) AS gates,
             count(*) FILTER (WHERE barrier = 'entrance') AS entrances,
             count(*) FILTER (WHERE barrier IN ('wall','fence','hedge')) AS barrier_ways,
             (SELECT count(*) FROM encl) AS enclosures,
             (SELECT round(ST_Area_Spheroid(ST_FlipCoordinates(g))/1e6,2) FROM cap) AS cap_km2,
             (SELECT count(*) FROM pl) AS places
      FROM ctxc) TO '{out}/cap-ctx.csv' (HEADER);
"""
if not os.path.exists(f'{out}/cap-pairs.csv'):
    duck(sql)
    print('pass B done', flush=True)
