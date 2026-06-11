from types import SimpleNamespace

import pandas as pd

from app.ui.dashboard import _combined_error_csv


def test_combined_error_csv_merges_all_error_files(tmp_path):
    decoded_dir = tmp_path / "decoded"
    decoded_dir.mkdir()
    pd.DataFrame(
        [{"source_file": "a.csv", "row_index": 1, "error": "bad a"}]
    ).to_csv(decoded_dir / "a_decode_errors.csv", index=False)
    pd.DataFrame(
        [{"source_file": "b.csv", "row_index": 2, "error": "bad b"}]
    ).to_csv(decoded_dir / "b_decode_errors.csv", index=False)

    payload = _combined_error_csv(SimpleNamespace(decoded_dir=decoded_dir))
    result = pd.read_csv(pd.io.common.BytesIO(payload))

    assert len(result) == 2
    assert set(result["source_file"]) == {"a.csv", "b.csv"}
