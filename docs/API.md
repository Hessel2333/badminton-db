# Static API

Base: `https://hessel2333.github.io/badminton-db`

All endpoints are static JSON served over HTTPS. The public API contract is `v1`.
Read `dataVersion` before refreshing a local cache. For a fixed, reproducible
snapshot, use the release ZIP rather than the moving `v1` URLs.

| Path | Content |
| --- | --- |
| `/v1/manifest.json` | Versions, counts, quality statement and relative endpoint paths |
| `/v1/catalog.json` | Full brands, products, media metadata and sources |
| `/v1/catalog.json.gz` | The same catalog compressed with gzip |
| `/v1/products/index.json` | Product summaries and `bySlug` lookup to stable UUIDs |
| `/v1/products/<uuid>.json` | One product |
| `/v1/brands/index.json` | All brands |
| `/v1/brands/<id>.json` | One brand and related product UUIDs |
| `/v1/categories/index.json` | Category IDs, names and product counts |
| `/v1/media/index.json` | Media metadata and count of distributable images |
| `/v1/media/<id>.json` | One media record; `downloadUrl` is nullable |
| `/v1/sources/index.json` | Source registry |
| `/v1/sources/<id>.json` | One source/import/processing record |
| `/v1/search.json` | Search terms and normalized text, keyed by product UUID |
| `/schemas/<kind>.schema.json` | JSON Schema 2020-12 |
| `/checksums.json` | SHA-256 for exported files, excluding this checksum file |
| `/exports/ios/equipment_catalog.json` | Existing iOS seed format |
| `/exports/ios/media-map.json` | Legacy image-key links to public media metadata |

The checksum paths are relative to the API base, not the manifest directory.
Links within `/v1/manifest.json` are relative to that manifest. JSON filenames are
case-sensitive; product UUIDs and data-file IDs are lowercase.

## Example lookup

```js
const base = "https://hessel2333.github.io/badminton-db";
const index = await fetch(`${base}/v1/products/index.json`).then(r => r.json());
const id = index.bySlug["victor-champion-no1"];
const product = await fetch(`${base}/v1/products/${id}.json`).then(r => r.json());
```

Join `brandId` to brands, `mediaIds` to media metadata, and `sourceIds` to sources.
A source registry entry records evidence or an import origin; it is not an
automatic verification of every linked assertion. Optional `fieldSources` can
identify evidence for individual fields.

## Quality and media behavior

- Initial product records are `unverified`. Clients should expose or respect
  their verification status rather than presenting the catalog as authoritative.
- Missing values are `null` or an empty collection, not guessed defaults.
- `curation.tags` and legacy popularity are imported curation, not measured ratings.
- Undated `legacy-reference` price observations are not current retail offers.
- `downloadUrl: null` means no image is distributed. Do not construct a photo URL
  from `fileName`, a legacy image key, a hash, or a known manufacturer's domain.
- A generated packaging image is not an official product photo. Its illustrative
  identifiers never become searchable product GTINs or manufacturer identifiers.

## Client updates

Cache the last valid snapshot, compare data versions, validate downloaded JSON
and checksums, then replace a cache atomically. An unavailable endpoint or a
failed check should leave the previous local snapshot usable. Fetching product
data does not require uploading personal collections to BadmintonDB.

To serve a build locally:

```sh
python scripts/catalog.py build
python -m http.server 8000 --directory dist
```

Then open `http://localhost:8000/v1/manifest.json`.
