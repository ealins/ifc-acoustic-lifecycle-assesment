from fair_platform.sldv_payload import inspect_sldv_payload


def test_inspects_library_style_sldv_txt_without_fixed_row_count():
    payload = (
        "header 1\nheader 2\n"
        "Point Index:\t7\t[x = 0.1 y = 0.2 z = 0.3]\n"
        "Frequency\tXreal\tXimag\n"
        "20\t1.0\t0.1\n"
        "21\t2.0\t0.2\n"
        "22\t3.0\t0.3\n"
    ).encode("latin-1")

    result = inspect_sldv_payload("new_scan.txt", payload)

    assert result["supported"] is True
    assert result["point_header"]["index"] == 7
    assert result["point_header"]["x"] == 0.1
    assert result["numeric_row_count"] == 3
    assert result["numeric_column_count"] == 3
    assert result["candidate_axis"]["start"] == 20.0
    assert result["candidate_axis"]["end"] == 22.0
    assert result["candidate_axis"]["step_if_uniform"] == 1.0
    assert result["source_preserved"] is True


def test_csv_inspection_does_not_assume_fixed_columns_or_frequency_range():
    payload = b"frequency,velocity,phase\n100,0.2,0.3\n200,0.4,0.5\n"

    result = inspect_sldv_payload("new_scan.csv", payload)

    assert result["numeric_row_count"] == 2
    assert result["numeric_column_count"] == 3
    assert result["candidate_axis"]["start"] == 100.0
    assert result["candidate_axis"]["end"] == 200.0


def test_inspection_preserves_legacy_encoding_and_semicolon_decimal_data():
    payload = "frequency;velocity_µm_s\n20,0;1,25\n21,0;1,50\n".encode("cp1252")

    result = inspect_sldv_payload("scan.csv", payload)

    assert result["encoding_used_for_inspection"] == "cp1252"
    assert result["numeric_row_count"] == 2
    assert result["numeric_column_count"] == 2
    assert result["candidate_axis"]["start"] == 20.0


def test_rejects_hdf5_as_thesis_payload_without_converting_it():
    result = inspect_sldv_payload("scan.h5", b"opaque")

    assert result["supported"] is False
    assert "txt" in result["reason"].lower()
    assert "csv" in result["reason"].lower()
