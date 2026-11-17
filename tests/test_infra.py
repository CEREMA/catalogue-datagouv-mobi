"""Infrastructure testable sans base ni réseau : lecture des exports."""

import pytest

from catalogue_mobi.infra_catalog import latest_export_urls
from catalogue_mobi.infra_csv import read_resource_stats


def _resource(title, fmt="csv"):
    return {"title": title, "format": fmt, "url": f"https://static/{title}"}


def test_latest_export_urls_takes_most_recent_of_each_export():
    resources = [
        _resource("export-dataset-20261116-055149.csv"),
        _resource("export-dataset-20261117-055149.csv"),
        _resource("export-dataservice-20261117-061516.csv"),  # pas suivi
        _resource("export-organization-20261117-061335.csv"),
        _resource("export-resource-20261117-060441.csv"),
    ]

    assert latest_export_urls(resources) == {
        "export-dataset.csv": "https://static/export-dataset-20261117-055149.csv",
        "export-organization.csv": "https://static/export-organization-20261117-061335.csv",
        "export-resource.csv": "https://static/export-resource-20261117-060441.csv",
    }


def test_latest_export_urls_fails_if_an_export_is_missing():
    with pytest.raises(RuntimeError):
        latest_export_urls([_resource("export-dataset-20261117-055149.csv")])


def test_read_resource_stats(tmp_path):
    path = tmp_path / "export-resource.csv"
    header = '"dataset.id";"title";"modified";"harvest.modified_at";"schema_name";"extras"\n'
    path.write_text(
        header
        + '"a";"r1";"2026-11-13T15:23:14";"";"etalab/schema-irve-statique";"{}"\n'
        + '"a";"r2\nsur deux lignes";"2026-11-15T08:00:00.123000";"";"";""\n'
        + '"a";"r3";"2026-01-01T00:00:00";"";"etalab/schema-irve-dynamique";"{}"\n'
        + '"b";"r4";"";"";"";""\n'
        # moissonnée : la date du moissonnage prime sur `modified`
        + '"c";"r5";"2026-11-17T00:00:00";"2023-06-29T00:00:00+00:00";"";"{}"\n'
        # fichier distant : la date détectée par l'analyse prime sur `modified`
        + '"d";"r6";"2026-11-17T00:00:00";"";"";'
        + '"{""analysis:last-modified-at"": ""2025-02-03T04:05:06Z""}"\n'
    )

    stats = sorted(read_resource_stats(path), key=lambda r: r["id"])

    assert stats == [
        {
            "id": "a",
            "last_update": "2026-11-15T08:00:00",
            "schemas": "etalab/schema-irve-dynamique,etalab/schema-irve-statique",
        },
        {"id": "b", "last_update": None, "schemas": None},
        {"id": "c", "last_update": "2023-06-29T00:00:00", "schemas": None},
        {"id": "d", "last_update": "2025-02-03T04:05:06", "schemas": None},
    ]
