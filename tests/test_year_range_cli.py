from pathlib import Path


def test_cli_defines_year_range_options():
    source = Path("cinescrapper/__main__.py").read_text()
    assert 'add_argument("--start-year"' in source
    assert 'add_argument("--end-year"' in source
    assert "args.start_year > args.end_year" in source
