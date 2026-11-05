# iOS integration

`python scripts/catalog.py build` generates
`dist/exports/ios/equipment_catalog.json` in the existing Swift `CatalogSeedFile`
shape. Version 0.1.0 exports catalog version 8 and preserves all 73 product UUIDs,
existing model data, image keys and legacy reference-price values.

For the initial tracker integration:

1. Keep the currently installed image binaries and `gear-image-manifest.json`.
2. Replace the source seed file in the iOS project with the generated seed.
3. Build and run the app. Its existing catalog-version import applies the snapshot
   while user equipment and purchase history retain their stable links.
4. Verify the bundle contains the expected image resources. Public BadmintonDB
   image metadata alone does not provide those binaries.

`media-map.json` links existing resource keys to asset records. A null download
URL must not erase a client's existing image or be turned into an inferred URL.
An app can retain its own permitted bundled media independently of this dataset.

No Swift client SDK or automatic network updater is shipped in v0.1.0. The app
can remain fully offline by bundling a release snapshot. A future updater should
check the manifest and schema, verify hashes, then install a validated snapshot
atomically with a last-known-good fallback. Collection, purchase, stock,
consumption and private media stay in the app's own data store.

The initial release does not modify the tracker app automatically; it provides
the independent source data and reproducible export needed to adopt that workflow.
