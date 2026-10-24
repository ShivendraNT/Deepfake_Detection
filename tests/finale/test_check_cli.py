"""`satya scan`: grades named files per channel; skips the kit manifest; keeps nothing."""

from __future__ import annotations

from satyapan.check_cli import expected, files_in, grade


def test_expected_answer_comes_from_the_file_name() -> None:
    assert expected("fake_voice_itw_01.wav") == "flag"
    assert expected("scam_text_uci_sms_03.txt") == "flag"
    assert expected("real_photo_dfdc_x.jpg") == "pass"
    assert expected("notes.txt") is None


def test_grade_counts_per_channel_and_overall() -> None:
    rows = [
        {"channel": "manual", "expected": "flag", "correct": "True"},
        {"channel": "manual", "expected": "pass", "correct": "False"},
        {"channel": "image", "expected": "flag", "correct": "False"},
        {"channel": "image", "expected": "", "correct": ""},  # not graded
    ]
    table = grade(rows)
    assert "| image | 0/1 | 0/0 | 0/1 |" in table
    assert "| manual | 1/1 | 0/1 | 1/2 |" in table
    assert table[-1] == "| ALL | 1/2 | 0/1 | 1/3 |"


def test_the_kit_manifest_is_not_scanned(tmp_path) -> None:
    (tmp_path / "kit_manifest.json").write_text("{}")
    (tmp_path / "scam_text_a.txt").write_text("share the OTP")
    assert [f.name for f in files_in([str(tmp_path)])] == ["scam_text_a.txt"]
