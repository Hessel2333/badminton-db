# Data model

## Identity and organization

Products use permanent UUIDs. The first release retains all 73 existing tracker
UUIDs. Slugs are readable lookup keys, not a replacement for persistent IDs.
Names, aliases, images and corrected specifications may change without changing
the product UUID.

Each product is stored at `data/products/<brand>/<model>.json`. Brand and source
records use stable lowercase IDs. Categories are `racket`, `shuttlecock`, `shoes`
and `other`. The schema files define allowed fields and reject unexpected ones.

## Model, variants and packaging

`model` is the model designation; `series` is its family when known. `variant`
can record a distinct color/edition, generation and label. `relations.variantOf`
can link separately cataloged variants once the relationship is evidenced.
The validator rejects missing parents, self-links, cross-brand links and cycles.

The initial import keeps existing white-tiger/green/VA entries separate and does
not infer their generation or parent relation from filenames. Weight/grip choices,
shoe sizes, shuttle speeds and new packaging are not automatically new models.
Contributors should document whether a difference is a separate model, a
purchasable variant, or an image/packaging revision before adding an ID.

## Names and evidence

Names support `zh-CN` and nullable English. Aliases are scoped to a brand and
category, preventing an identical nickname from conflating different brands.
Normalization uses Unicode NFKC, case folding and alphanumeric characters.

`provenance.verification` is `unverified` or `verified`. `sourceIds` link to
`data/sources/`; optional `fieldSources` map field names to the evidence that
supports them. An imported catalog and a manufacturer's product page are
different source types. Add exact product-page URLs when available, record
retrieval dates, and do not upgrade review status solely because a source exists.

## Prices and legacy compatibility

Legacy reference prices are observations with currency, region, nullable date,
source IDs and review status. Their undated values remain unverified. Actual
personal purchase prices are not part of the public catalog.

The `legacy` object preserves existing image keys, ranking metadata, revisions
and catalog timestamps for the compatibility export. These timestamps describe
catalog records, not product launch dates; popularity is not a community rating.

## Media

Image records live in `media/metadata/`, independently of product records.
They contain product links, legacy resource keys, dimensions, SHA-256, origin,
processing/derivation history and explicit distribution rights.

- `photo`: a photograph, with provenance identifying its origin.
- `processed-image`: a processed/cutout image whose original nature is not assumed.
- `generated-render`: generated or reconstructed product artwork.
- `illustration`: another clearly identified visual representation.

Every initial asset is withheld and has no public file or download URL. A hash
identifies a known local file but does not grant permission to share it.
Openly licensed files require approved rights, holder, evidence URL, matching
checksum and an explicit path under `media/files/`. The metadata license does
not relicense the depicted packaging, manufacturer marks or source photographs.

Illustrative numbers belong only in media `syntheticIdentifiers`. The fixed
VICTOR barcode is not stored as a product GTIN, model code or alternate ID.

## Source and generated files

Edit the files in `data/` and `media/metadata/`, their schemas, and the ordered
asset IDs in `media/manifest.json`. Build exports from them; never edit `dist/`
or the generated iOS seed directly. Raise `dataVersion` for a dataset release,
`catalogVersion` when shipping a changed iOS seed, and a record's `revision` when
changing that record. Preserve IDs on corrections and retire catalog entries
with `curation.listed: false` rather than deleting referenced historical models.
