"""Invariants of the listing: every synced plugin has a seeded entry, Milieu's row and entry are what its release
pipeline expects (solona-m/milieu docs/adr/0007), and repo.json stays in the format the sync's jq writes.

Run from the repository root:  python -m unittest discover -s tests -v
"""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPO_JSON = ROOT / "repo.json"
SYNC_YML = ROOT / ".github" / "workflows" / "sync.yml"

MILIEU_ICON = "https://dl.solona.info/milieu/icon.png"
MILIEU_ROW = "Milieu|solona-m/milieu|Milieu.json|milieu/|" + MILIEU_ICON
# The dl.solona.info worker's route for Milieu's plugin zips.
MILIEU_LINK = re.compile(r"^https://dl\.solona\.info/milieu/(v[0-9][0-9.]{0,30}|testing-[0-9]+)/latest\.zip$")
MILIEU_STABLE_LINK = re.compile(r"^https://dl\.solona\.info/milieu/v[0-9][0-9.]{0,30}/latest\.zip$")
MILIEU_TESTING_LINK = re.compile(r"^https://dl\.solona\.info/milieu/testing-[0-9]+/latest\.zip$")


def load_text():
    return REPO_JSON.read_bytes().decode("utf-8")


def load_entries():
    return json.loads(load_text())


def plugin_rows():
    """The quoted rows of the PLUGINS=( ... ) table in sync.yml, as lists of their five fields."""
    lines = SYNC_YML.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "PLUGINS=(")
    rows = []
    for line in lines[start + 1:]:
        s = line.strip()
        if s == ")":
            break
        m = re.fullmatch(r'"([^"]*)"', s)
        if m:
            rows.append(m.group(1))
    return rows


def milieu():
    matches = [e for e in load_entries() if e.get("InternalName") == "Milieu"]
    assert len(matches) == 1, f"expected one Milieu entry, found {len(matches)}"
    return matches[0]


class ListingTests(unittest.TestCase):
    # [AC-plugin-release-5] [EDGE-plugin-release-13]
    def test_every_synced_plugin_has_a_seeded_entry(self):
        entries = load_entries()
        rows = plugin_rows()
        self.assertGreaterEqual(len(rows), 3)
        for row in rows:
            name = row.split("|")[0]
            count = sum(1 for e in entries if e.get("InternalName") == name)
            self.assertEqual(count, 1, f"{name}: {count} repo.json entries (the sync only updates existing ones)")

    # [AC-plugin-release-5]
    def test_milieu_row(self):
        self.assertIn(MILIEU_ROW, plugin_rows())

    # [AC-plugin-release-5]
    def test_milieu_seed_entry(self):
        # The sync merges Milieu's whole manifest over this entry, so identity, the API levels, ApplicableVersion and
        # RepoUrl come from the manifest too: these are the values it carries today, and this test must be updated
        # with it (an API bump, for one). IsHide, IsTestingExclusive and IconUrl are repo.json's own. What changes
        # from release to release is not pinned: Description, Punchline and the tags, and the sync's versions,
        # LastUpdate and DownloadCount (solona-m/milieu ADR 0007). The publish run checks the versions itself.
        e = milieu()
        expected = {
            "Author": "Solona",
            "Name": "Milieu",
            "InternalName": "Milieu",
            "ApplicableVersion": "any",
            "DalamudApiLevel": 15,
            "TestingDalamudApiLevel": 15,
            "IsHide": False,
            "RepoUrl": "https://github.com/solona-m/milieu",
            "IconUrl": MILIEU_ICON,
        }
        for key, value in expected.items():
            self.assertEqual(e.get(key), value, key)
        self.assertIsInstance(e.get("IsTestingExclusive"), bool)
        for key in ("DownloadLinkInstall", "DownloadLinkTesting", "DownloadLinkUpdate"):
            self.assertRegex(e.get(key, ""), MILIEU_LINK, key)
        self.assertRegex(e["DownloadLinkTesting"], MILIEU_TESTING_LINK)

    # [AC-plugin-release-8]
    def test_milieu_icon_is_the_mirror_icon(self):
        row = next(r for r in plugin_rows() if r.split("|")[0] == "Milieu")
        self.assertEqual(row.split("|")[4], MILIEU_ICON)
        self.assertEqual(milieu()["IconUrl"], MILIEU_ICON)

    # [EDGE-plugin-release-14]
    def test_internal_names_and_prefixes_unique(self):
        names = [e.get("InternalName") for e in load_entries()]
        self.assertEqual(len(names), len(set(names)), names)
        prefixes = [r.split("|")[3] for r in plugin_rows() if r.split("|")[3]]
        self.assertEqual(len(prefixes), len(set(prefixes)), prefixes)
        for p in prefixes:
            self.assertTrue(p.endswith("/"), p)

    # [AC-plugin-release-10] [EDGE-plugin-release-31]
    def test_milieu_links_match_testing_exclusivity(self):
        e = milieu()
        if e["IsTestingExclusive"] is False:
            # Listed for everyone: Install and Update must be a stable build, never a testing one.
            for key in ("DownloadLinkInstall", "DownloadLinkUpdate"):
                self.assertRegex(e[key], MILIEU_STABLE_LINK, key)
        else:
            for key in ("DownloadLinkInstall", "DownloadLinkUpdate"):
                self.assertRegex(e[key], MILIEU_LINK, key)

    # [EDGE-plugin-release-19]
    def test_repo_json_keeps_the_jq_format(self):
        raw = REPO_JSON.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertTrue(raw.endswith(b"]\n"))
        text = raw.decode("utf-8")
        self.assertEqual(text, json.dumps(json.loads(text), indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    unittest.main()
