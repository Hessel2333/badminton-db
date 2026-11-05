# BadmintonDB

An open, versioned badminton equipment catalog for apps and community projects.

[简体中文](README.zh-CN.md) · [API](docs/API.md) · [Data model](docs/DATA_MODEL.md) · [Contributing](CONTRIBUTING.md) · [Licensing](LICENSES.md)

**v0.1.0:** 10 brands, 73 products (46 shuttlecocks, 20 rackets, 7 shoes),
69 image-metadata records, and **0 redistributed images**.

This is an initial catalog import, not a manufacturer-verified database. Every
initial product is marked `unverified`. Legacy prices are undated reference
observations, not current retail prices. Unknown specifications remain `null`.

## Use the data

The API is static JSON, published on GitHub Pages. No API key is required.

```text
https://hessel2333.github.io/badminton-db/v1/manifest.json
https://hessel2333.github.io/badminton-db/v1/products/index.json
https://hessel2333.github.io/badminton-db/v1/catalog.json
https://hessel2333.github.io/badminton-db/exports/ios/equipment_catalog.json
```

```python
import json
from urllib.request import urlopen

base = "https://hessel2333.github.io/badminton-db"
catalog = json.load(urlopen(base + "/v1/catalog.json"))
victor_shuttles = [p for p in catalog["products"]
                  if p["brandId"] == "victor" and p["category"] == "shuttlecock"]
```

For reproducible offline use, download a [tagged release](https://github.com/Hessel2333/badminton-db/releases)
and verify its `SHA256SUMS`. The `v1` API tracks the current data release;
`dataVersion` identifies the dataset and `schemaVersion` identifies its contract.

## What's in the repository

```text
data/
  manifest.json                  # Dataset and compatibility-export versions
  brands/*.json                  # Canonical brand names and aliases
  products/<brand>/*.json         # One product per file; stable existing UUIDs
  sources/*.json                  # Sources and import/processing provenance
media/
  manifest.json
  metadata/*.json                 # Image identity, provenance, rights and hashes
  files/                         # Only explicitly approved, licensed files
schemas/*.schema.json             # JSON Schema 2020-12
scripts/catalog.py               # Validate, build static API, package releases
tests/
docs/
```

Product names, identifiers, variants, evidence and media references are separated
from personal collections. This repository contains no purchase history,
inventory, consumption, private notes, user photos or tracker database backups.
Existing product UUIDs are retained so client apps can keep their references.

## Images and provenance

All initial image records are metadata-only with `distribution.status: withheld`
and no download URL. Original photos and processed images have not been uploaded.
Permission must be documented before a file can be distributed; see
[licensing scopes](LICENSES.md) and [media contribution rules](CONTRIBUTING.md).

The 15 VICTOR packaging illustrations are identified as reconstructed renders,
not official photos. Their fixed barcode `1234567890128` is recorded only as an
illustrative identifier in image metadata, never as a product GTIN or SKU.

## Validate and build

Python 3.11 or later is required.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/catalog.py validate
python -m unittest discover -s tests -v
python scripts/catalog.py build
python scripts/catalog.py package
```

`dist/` contains the static API, schemas, checksums and iOS compatibility export.
`output/` contains the versioned ZIP and `SHA256SUMS`. Both are generated and
ignored by Git. GitHub Actions validates changes and publishes the API from `main`.

The iOS export retains the existing catalog UUIDs, image keys, catalog version,
and legacy reference-price values. It **does not replace existing bundled images**
with unavailable media. New clients should consult image metadata and handle
`downloadUrl: null` explicitly. See [iOS integration](docs/IOS.md).

## Contribute

Add evidence-backed corrections or missing models through a pull request.
Use the [contribution guide](CONTRIBUTING.md), keep existing UUIDs stable, distinguish
generations and packaging changes, and leave unsupported fields unknown.

## Licenses and inspiration

Tooling, schemas and documentation: [MIT](LICENSE).
Original metadata curation: [CC BY 4.0](LICENSE-DATA).
Media: each file's explicit terms, documented separately in its metadata.
These licenses do not grant rights in third-party imagery or trademarks.

The public-data/client-app separation is inspired by
[AppleDB](https://github.com/littlebyteorg/appledb) and
[Hoardware](https://apps.apple.com/us/app/hoardware-device-collection/id6806893785).
The initial metadata was imported from the
[badminton_tracker](https://github.com/Hessel2333/badminton_tracker) catalog;
[migration details](docs/migration.json) record the snapshot and preserved IDs.
