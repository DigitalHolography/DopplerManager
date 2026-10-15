from doppler_manager.models import AcquisitionResult, StageResult


def test_acquisition_row_includes_deduplicated_warning_messages() -> None:
    shared_warning = "Manual review requested."
    acquisition = AcquisitionResult(
        acquisition_id="251031_ALA_L_1",
        warnings=[shared_warning],
        stages={
            "dv": StageResult(code="dv", label="DopplerView", status="partial"),
            "ef": StageResult(
                code="ef",
                label="EyeFlow",
                status="warning",
                notes=[shared_warning, "A .h5 file is present, but the expected name is 251031_ALA_L_1_EF.h5."],
            ),
            "ae": StageResult(code="ae", label="AngioEye", status="warning"),
        },
    )

    assert acquisition.warning_messages() == [
        shared_warning,
        "EF: A .h5 file is present, but the expected name is 251031_ALA_L_1_EF.h5.",
        "AE: Needs review.",
    ]
    assert acquisition.to_row()["warnings"] == 3
