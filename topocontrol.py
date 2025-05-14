    #!/usr/bin/env python3
"""
topocontrol.py - Sjekk topologiregler i et GeoJSON og skriv ut detaljert rapport over feilaktige geometrier.

Eksempel på forenklet bruk:
  python topocontrol.py -i geometri.geojson

Eksempel på avansert bruk:
  python topocontrol.py -i geometri.geojson -u egendefinert_errorfil.geojson -t 2.0 -e 25832

Forklaringer:
  -i, Navn på innfil i .geojson-format.
  -u, Egendefinert navn på utfil (default error_YYYYMMDD_HHMM.geojson)
  -t, Avstandsterskel i meter for "nære" objekter (default: 1.0)
  -e, EPSG-kode for reprojisering (default: 25832)
"""
import sys
import os
import signal
from datetime import datetime

# Sett signal handler for å avbryte
def signal_handler(sig, frame):
    print("\nAvbrutt av bruker. Avslutter...", file=sys.stderr)
    sys.exit(1)
signal.signal(signal.SIGINT, signal_handler)

# Sjekk at nødvendige moduler er installert
try:
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry
    from shapely.geometry import LineString
except ImportError as e:
    missing = str(e).split("'")[1]
    print(f"Modulen '{missing}' er ikke installert. Installer med: conda install -c conda-forge geopandas shapely", file=sys.stderr)
    sys.exit(1)

# Progressbar støttes via tqdm
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

import argparse
from itertools import combinations


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sjekk topologiregler i et GeoJSON og lag en rapport over feilaktige geometrier."
    )
    parser.add_argument("-i", "--innfil", required=True, help="GeoJSON-innfil")
    parser.add_argument("-u", "--utfil", default=None, help="GeoJSON-utfil med feil-geometrier (default: error_YYYYMMDD_HHMM.geojson)")
    parser.add_argument("-t", "--terskel", type=float, default=1.0,
                        help="Avstandsterskel i meter for 'nære' objekter (default: 1.0)")
    parser.add_argument("-e", "--epsg", type=int, default=25832,
                        help="EPSG-kode for reprojisering (default: 25832)")
    return parser.parse_args()


def main():
    args = parse_args()

    # Tidspunkt
    nowreport = datetime.now().strftime('%Y.%m.%d, %H:%M')
    now = datetime.now().strftime('%Y%m%d_%H%M')
    # Bestem navn på utfil
    if args.utfil:
        utfil_geojson = args.utfil
    else:
        utfil_geojson = f"error_{now}.geojson"

    report_filename = f"report_{now}.txt"
    report_lines = []
    report_lines.append(f"Kjøringstidspunkt: {nowreport}")
    report_lines.append(f"Reprojiserer til EPSG:{args.epsg}, terskel={args.terskel} m")
    print(f"Kjøringstidspunkt: {nowreport}")
    print(f"Reprojiserer til EPSG:{args.epsg}, terskel={args.terskel} m")

    # Last inn fil
    print(f"Laster inn GeoJSON '{args.innfil}'... (CTRL-C for å avbryte!)")
    try:
        gdf = gpd.read_file(args.innfil)
    except Exception as e:
        print(f"Feil ved lesing av '{args.innfil}': {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Lest inn {len(gdf)} objekter.")
    report_lines.append(f"Antall objekter: {len(gdf)}")

    # Reprojiser
    try:
        gdf = gdf.to_crs(epsg=args.epsg)
    except Exception as e:
        print(f"Feil ved reprojisering: {e}", file=sys.stderr)
        sys.exit(1)

    # Forbered datastrukturer for feil
    sets = {key: set() for key in ['selfcross', 'invalid', 'duplicate', 'overlap', 'near']}
    sets['all'] = set()

    n = len(gdf)
    # Enkeltsjekk
    for idx in tqdm(range(n), desc="Enkeltsjekk"):
        geom = gdf.geometry.iloc[idx]
        if isinstance(geom, LineString) and not geom.is_simple:
            sets['selfcross'].add(idx);
            sets['all'].add(idx)
        elif isinstance(geom, BaseGeometry) and not geom.is_valid:
            sets['invalid'].add(idx);
            sets['all'].add(idx)

    # Parvis sjekk
    total_pairs = n * (n - 1) // 2
    for idx1, idx2 in tqdm(combinations(range(n), 2), total=total_pairs, desc="Parvis sjekk"):
        geom1 = gdf.geometry.iloc[idx1]
        geom2 = gdf.geometry.iloc[idx2]
        if geom1.equals(geom2):
            sets['duplicate'].update([idx1, idx2]); sets['all'].update([idx1, idx2])
        elif geom1.intersects(geom2) and not geom1.touches(geom2):
            sets['overlap'].update([idx1, idx2]); sets['all'].update([idx1, idx2])
        elif geom1.distance(geom2) < args.terskel:
            sets['near'].update([idx1, idx2]); sets['all'].update([idx1, idx2])

    # Sammendragsrapport
    summary = [
        f"Antall selvkryssende linjer: {len(sets['selfcross'])}",
        f"Antall ugyldige geometrier: {len(sets['invalid'])}",
        f"Antall duplikat-geometrier: {len(sets['duplicate'])}",
        f"Antall kryssende geometrier: {len(sets['overlap'])}",
        f"Antall for-nære geometrier (<{args.terskel}m): {len(sets['near'])}",
        f"Totalt unike objekter med feil: {len(sets['all'])}"
    ]
    print("Sammendrag:")
    report_lines.append("Sammendrag:")
    for line in summary:
        print(f"  {line}"); report_lines.append(line)

    # Skriv feil-geometrier
    if sets['all']:
        try:
            error_gdf = gdf.loc[sorted(sets['all'])]
            error_gdf.to_file(utfil_geojson, driver="GeoJSON")
            msg = f"Skrevet {len(sets['all'])} objekter til '{utfil_geojson}'"
            print(msg); report_lines.append(msg)
        except Exception as e:
            print(f"Feil ved skriving til '{utfil_geojson}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        no_err = "Ingen feil funnet."
        print(no_err); report_lines.append(no_err)

    # Lagre rapport
    try:
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(os.linesep.join(report_lines))
        print(f"Rapport lagret som '{report_filename}'.")
    except Exception as e:
        print(f"Feil ved skriving av rapport: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
