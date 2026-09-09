from fair_platform.measurement import inspect_measurement


def test_xml_inspection_detects_frequency_signal():
    result = inspect_measurement(
        "measurement.xml",
        b"<VaBDat><FrequencyHz>100</FrequencyHz><Rw>52</Rw></VaBDat>",
    )
    assert result["valid"] is True
    assert result["details"]["root_element"] == "VaBDat"
    assert "frequency" in result["semantic_signals"]
    assert "sound_reduction" in result["semantic_signals"]


def test_csv_inspection_reports_columns_and_preview():
    result = inspect_measurement(
        "spectrum.csv",
        b"frequency_hz,sound_reduction_db\n100,32.1\n125,34.2\n",
    )
    assert result["valid"] is True
    assert result["details"]["sampled_rows"] == 2
    assert result["details"]["columns"] == ["frequency_hz", "sound_reduction_db"]
    assert "frequency" in result["semantic_signals"]


def test_vtk_inspection_reports_structure():
    payload = b"# vtk DataFile Version 3.0\nmode shape\nASCII\nDATASET POLYDATA\nPOINTS 4 float\n0 0 0 1 0 0 1 1 0 0 1 0\nPOLYGONS 1 5\n4 0 1 2 3\nPOINT_DATA 4\nVECTORS displacement float\n"
    result = inspect_measurement("mode.vtk", payload)
    assert result["valid"] is True
    assert result["details"]["dataset_type"] == "POLYDATA"
    assert result["details"]["counts"]["points"] == 4
    assert "vibration" in result["semantic_signals"]


def test_empty_payload_is_invalid():
    result = inspect_measurement("empty.dat", b"")
    assert result["valid"] is False
    assert result["warnings"]
