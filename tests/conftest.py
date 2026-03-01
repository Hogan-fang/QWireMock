from pathlib import Path

import pytest


_V2_CASE_RESULTS: list[dict[str, str]] = []


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "case(point, keyword='N/A'): annotate testcase with test point and order keyword",
    )


@pytest.fixture
def record_order_keyword(request: pytest.FixtureRequest):
    def _record(keyword: str) -> None:
        request.node.user_properties.append(("order_keyword", str(keyword)))

    return _record


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    outcome = yield
    report = outcome.get_result()

    if report.when != "call":
        return

    is_v2_case = "test_v2_" in item.nodeid
    marker = item.get_closest_marker("case")
    if not is_v2_case and marker is None:
        return

    point = "Unlabeled test point"
    keyword = "N/A"
    if marker is not None:
        point = str(marker.kwargs.get("point", point))
        keyword = str(marker.kwargs.get("keyword", keyword))

    for key, value in item.user_properties:
        if key == "order_keyword":
            keyword = str(value)

    _V2_CASE_RESULTS.append(
        {
            "case": item.name,
            "status": report.outcome,
            "point": point,
            "keyword": keyword,
        }
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if not _V2_CASE_RESULTS:
        return

    report_dir = Path("tests/reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_file = report_dir / "v2-test-execution-report.md"

    passed = sum(1 for row in _V2_CASE_RESULTS if row["status"] == "passed")
    failed = sum(1 for row in _V2_CASE_RESULTS if row["status"] == "failed")
    skipped = sum(1 for row in _V2_CASE_RESULTS if row["status"] == "skipped")

    lines = [
        "# V2 Test Execution Report",
        "",
        f"- Total test cases: {len(_V2_CASE_RESULTS)}",
        f"- Passed: {passed}",
        f"- Failed: {failed}",
        f"- Skipped: {skipped}",
        "",
        "## Case Details",
        "| No. | Test Case | Result | Test Point | Order Keyword |",
        "|---:|---|---|---|---|",
    ]

    for index, row in enumerate(_V2_CASE_RESULTS, start=1):
        lines.append(
            f"| {index} | {row['case']} | {row['status']} | {row['point']} | {row['keyword']} |"
        )

    report_file.write_text("\n".join(lines), encoding="utf-8")
