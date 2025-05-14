topocontrol.py - Sjekk topologiregler i et GeoJSON og skriv ut detaljert rapport over feilaktige geometrier.

Eksempel på forenklet bruk:
python topocontrol.py -i geometri.geojson

Eksempel på avansert bruk:
python topocontrol.py -i geometri.geojson -u utfil.geojson -t 2.0 -e 25832

Forklaringer:
-i, Navn på innfil i .geojson-format.
-u, Egendefinert navn på utfil (default error_YYYYMMDD_HHMM.geojson)
-t, Avstandsterskel i meter for "nære" objekter (default: 1.0)
-e, EPSG-kode for reprojisering (default: 25832)
