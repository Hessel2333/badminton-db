import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import catalog

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "db"
        for folder in ("data", "media", "schemas"):
            shutil.copytree(ROOT / folder, root / folder)
        for name in ("LICENSE", "LICENSE-DATA"):
            shutil.copy2(ROOT / name, root / name)
        return root

    def product_file(self, root):
        return next((root / "data/products").glob("*/*.json"))

    def change(self, file, fn):
        record = catalog.read(file)
        fn(record)
        catalog.write(file, record)

    def test_baseline_retains_migrated_uuids_as_catalog_grows(self):
        data = catalog.validate()
        migration = catalog.read(ROOT / "docs/migration.json")
        self.assertTrue(set(migration["preservedProductIds"]) <= {p["id"] for p in data["products"]})
        self.assertGreaterEqual(data["stats"]["products"], migration["products"])
        self.assertGreaterEqual(data["stats"]["brands"], migration["brands"])

    def test_duplicate_json_keys_and_non_finite_values_are_rejected(self):
        root = self.fixture()
        file = self.product_file(root)
        file.write_text('{"id":"one","id":"two"}')
        with self.assertRaisesRegex(catalog.CatalogError, "Duplicate JSON"):
            catalog.validate(root)
        file.write_text('{"price":NaN}')
        with self.assertRaisesRegex(catalog.CatalogError, "Non-finite"):
            catalog.validate(root)

    def test_duplicate_uuid_rejected(self):
        root = self.fixture()
        first, second = list((root / "data/products").glob("*/*.json"))[:2]
        self.change(second, lambda record: record.update(id=catalog.read(first)["id"]))
        with self.assertRaisesRegex(catalog.CatalogError, "Duplicate products ID"):
            catalog.validate(root)

    def test_scoped_alias_conflicts_rejected(self):
        root = self.fixture()
        first, second = [p for p in sorted((root / "data/products/victor").glob("*.json")) if catalog.read(p)["category"] == "shuttlecock"][:2]
        name = catalog.read(first)["names"]["zh-CN"]
        self.change(second, lambda record: record["aliases"].append(name))
        with self.assertRaisesRegex(catalog.CatalogError, "conflicting scoped"):
            catalog.validate(root)

    def test_missing_media_and_evidence_references_rejected(self):
        root = self.fixture()
        file = self.product_file(root)
        self.change(file, lambda record: record["mediaIds"].append("missing-image"))
        self.change(file, lambda record: record["provenance"]["sourceIds"].append("missing-source"))
        with self.assertRaisesRegex(catalog.CatalogError, "unknown media ID"):
            catalog.validate(root)

    def test_unknown_private_fields_rejected(self):
        root = self.fixture()
        self.change(self.product_file(root), lambda record: record.update(purchaseDate="2026-11-05", personalNotes="private"))
        with self.assertRaisesRegex(catalog.CatalogError, "Additional properties"):
            catalog.validate(root)

    def test_unapproved_binary_cannot_enter_release(self):
        root = self.fixture()
        (root / "media/files/unapproved.png").write_bytes(b"not-an-approved-image")
        with self.assertRaisesRegex(catalog.CatalogError, "Unapproved/unreferenced image"):
            catalog.validate(root)

    def test_public_image_requires_permission_and_safe_path(self):
        root = self.fixture()
        file = next((root / "media/metadata").glob("*.json"))
        self.change(file, lambda record: record["rights"].update(status="unreviewed"))
        self.change(file, lambda record: record["distribution"].update(status="public", file="media/files/example.png"))
        with self.assertRaisesRegex(catalog.CatalogError, "approved rights"):
            catalog.validate(root)
        self.change(file, lambda record: record["distribution"].update(file="media/files/images/../../../data/manifest.json"))
        with self.assertRaisesRegex(catalog.CatalogError, "unsafe image path"):
            catalog.validate(root)

    def test_approved_licensed_asset_is_included_and_hash_checked(self):
        root = self.fixture()
        asset = catalog.read(next((root / "media/metadata").glob("*.json")))
        asset.update(id="test-owned-image", kind="illustration", fileName="test-owned-image.svg", legacyImageKeys=["test-owned-image"], syntheticIdentifiers=[], dimensions={"width":8,"height":8}, hasAlpha=False)
        body = b'<svg xmlns="http://www.w3.org/2000/svg" width="8" height="8"><rect width="8" height="8"/></svg>'
        image = root / "media/files/test-owned-image.svg"
        image.write_bytes(body)
        asset["rights"] = {"status": "approved", "license": "CC0-1.0", "holder": "Test contributor", "evidenceUrl": "https://example.com/permission"}
        asset["distribution"] = {"status": "public", "file": "media/files/test-owned-image.svg"}
        asset["sha256"] = hashlib.sha256(body).hexdigest()
        catalog.write(root / "media/metadata/test-owned-image.json", asset)
        for file in (root / "data/products").glob("*/*.json"):
            if catalog.read(file)["id"] in asset["productIds"]:
                self.change(file, lambda record: record["mediaIds"].append("test-owned-image"))
        self.change(root / "media/manifest.json", lambda record: record["metadataIds"].append("test-owned-image"))
        output = root / "dist"
        catalog.build(output, root)
        self.assertEqual((output / "media/files/test-owned-image.svg").read_bytes(), body)
        image.write_bytes(body + b"changed")
        with self.assertRaisesRegex(catalog.CatalogError, "checksum mismatch"):
            catalog.validate(root)

    def test_variant_cycles_rejected(self):
        root = self.fixture()
        a, b = list((root / "data/products/victor").glob("*.json"))[:2]
        aid, bid = catalog.read(a)["id"], catalog.read(b)["id"]
        self.change(a, lambda record: record["relations"].update(variantOf=bid))
        self.change(b, lambda record: record["relations"].update(variantOf=aid))
        with self.assertRaisesRegex(catalog.CatalogError, "cyclic variant"):
            catalog.validate(root)

    def test_build_is_deterministic_and_records_follow_published_schemas(self):
        root = self.fixture()
        first, second = root / "first", root / "second"
        catalog.build(first, root); catalog.build(second, root)
        self.assertEqual(catalog.read(first / "checksums.json"), catalog.read(second / "checksums.json"))
        for file, checksum in catalog.read(first / "checksums.json").items():
            self.assertEqual(hashlib.sha256((first / file).read_bytes()).hexdigest(), checksum)
        for folder, kind in [("products", "product"), ("brands", "brand"), ("media", "asset"), ("sources", "source")]:
            validator = catalog.Draft202012Validator(catalog.read(root / "schemas" / (kind + ".schema.json")))
            for file in (first / "v1" / folder).glob("*.json"):
                if file.name != "index.json":
                    validator.validate(catalog.read(file))
        for asset in catalog.read(first / "v1/media/index.json")["metadata"]:
            if asset["distribution"]["status"] == "withheld":
                self.assertIsNone(asset["downloadUrl"])
            else:
                self.assertTrue((first / asset["distribution"]["file"]).is_file())

    def test_ios_export_preserves_keys_prices_and_ids_without_personal_data(self):
        data = catalog.validate()
        seed = catalog.ios_seed(data)
        products = {p["id"]: p for p in data["products"]}
        self.assertEqual(seed["version"], data["manifest"]["catalogVersion"])
        self.assertEqual(len(seed["equipment"]), len(data["products"]))
        for entry in seed["equipment"]:
            p = products[entry["id"]]
            self.assertEqual(entry["imageKey"], p["legacy"]["imageKey"])
            expected_price = next((o["amount"] for o in p["priceObservations"] if o["kind"] == "legacy-reference" and o["currency"] == "CNY"), None)
            self.assertEqual(entry["suggestedUnitPriceCny"], expected_price)
        self.assertNotIn("personalNotes", json.dumps(seed))

    def test_build_cannot_overwrite_source_or_unrelated_folder(self):
        root = self.fixture()
        with self.assertRaisesRegex(catalog.CatalogError, "source repository"):
            catalog.build(root, root)
        folder = root / "unrelated"
        folder.mkdir(); (folder / "keep.txt").write_text("keep")
        with self.assertRaisesRegex(catalog.CatalogError, "non-build directory"):
            catalog.build(folder, root)
        self.assertEqual((folder / "keep.txt").read_text(), "keep")

    def test_fixed_render_barcode_never_becomes_product_identifier(self):
        data = catalog.validate()
        rendered = [a for a in data["assets"] if "victor-cylinder-v3" in a["provenance"]["sourceIds"]]
        self.assertGreaterEqual(len(rendered), 15)
        self.assertTrue(all(any(i["value"] == "1234567890128" and i["purpose"] == "illustrative-only" for i in a["syntheticIdentifiers"]) for a in rendered))
        self.assertTrue(all("gtin" not in p for p in data["products"]))

    def test_new_models_can_be_added_without_rewriting_historical_migration(self):
        root = self.fixture()
        first = catalog.read(self.product_file(root))
        first.update(id="b3d083b5-09d7-4379-84a1-d2c1223593ef", slug=first["brandId"] + "-test-new-model", model="TEST-NEW-MODEL", aliases=[], mediaIds=[])
        first["names"] = {"zh-CN": "新增测试型号", "en": None}
        first["legacy"]["imageKey"] = None
        catalog.write(root / "data/products" / first["brandId"] / "test-new-model.json", first)
        data = catalog.validate(root)
        migration = catalog.read(ROOT / "docs/migration.json")
        self.assertEqual(len(data["products"]), len(catalog.validate()["products"]) + 1)
        self.assertTrue(set(migration["preservedProductIds"]) <= {p["id"] for p in data["products"]})


if __name__ == "__main__":
    unittest.main()
