"""Skip the test modules that import pygmt when the GMT shared library is absent."""


def _gmt_unavailable_reason() -> str | None:
    try:
        import pygmt  # noqa: F401
    except Exception as error:
        # pygmt raises its own GMTCLibNotFoundError, which is not an ImportError.
        return str(error).splitlines()[0]
    return None


_GMT_REASON = _gmt_unavailable_reason()

# These modules import pygmt at the top level, so they fail at collection.
_GMT_MODULES = ("packages/tsdhn/tests/test_maxola.py",)

collect_ignore = list(_GMT_MODULES) if _GMT_REASON else []


def pytest_report_header(config: object) -> str | None:
    if _GMT_REASON is None:
        return None
    skipped = ", ".join(_GMT_MODULES)
    return f"gmt: not loadable ({_GMT_REASON}); not collected: {skipped}"
