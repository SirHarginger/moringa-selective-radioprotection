import math

import pandas as pd

from moringa_radioprotection.raw_activity import (
    build_raw_zscore_reconstruction,
    build_raw_zscore_reconstruction_summary,
)


def _raw_profile_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "NSC #": [101, 102],
            "Drug name": ["compound-a", "compound-b"],
            "PubChem SID": [1001, 1002],
            "BR:MCF7": ["4.0", "na"],
            "PR:DU-145": ["6.0", "7.0"],
            "LC:A549": ["na", "5.0"],
        }
    )


def _processed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "nsc_id": ["101", "102"],
            "mcf7_zscore": [-1.0, 0.5],
            "du145_zscore": [1.0, 1.0],
        }
    )


def test_zscore_reconstruction_treats_na_as_missing():
    reconstruction = build_raw_zscore_reconstruction(_raw_profile_frame(), _processed_frame())

    assert reconstruction[["nsc_id", "target"]].values.tolist() == [
        ["101", "MCF7"],
        ["101", "DU145"],
        ["102", "DU145"],
    ]
    first_compound = reconstruction[reconstruction["nsc_id"] == "101"].set_index("target")
    assert first_compound.loc["MCF7", "reconstructed_zscore_ddof0"] == -1.0
    assert first_compound.loc["DU145", "reconstructed_zscore_ddof0"] == 1.0
    assert math.isclose(
        first_compound.loc["MCF7", "reconstructed_zscore_ddof1"],
        -1 / math.sqrt(2),
    )


def test_zscore_reconstruction_summary_has_one_row_per_target_and_ddof():
    summary = build_raw_zscore_reconstruction_summary(_raw_profile_frame(), _processed_frame())

    assert summary[["target", "ddof"]].values.tolist() == [
        ["MCF7", 0],
        ["DU145", 0],
        ["MCF7", 1],
        ["DU145", 1],
    ]
