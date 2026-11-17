import pytest

from resume_builder.fit import fit_font_size


def pages_with_threshold(threshold: float):
    calls = []

    def count(size: float) -> int:
        calls.append(size)
        return 1 if size <= threshold else 2

    return count, calls


def test_uses_max_size_when_it_fits():
    count, calls = pages_with_threshold(99)

    result = fit_font_size(count, min_size=8, max_size=12)

    assert (result.font_size, result.fits, result.pages) == (12, True, 1)
    assert calls == [12]


def test_finds_the_largest_size_that_fits():
    count, _ = pages_with_threshold(10.37)

    result = fit_font_size(count, min_size=8, max_size=12, step=0.1)

    assert result.font_size == 10.3
    assert result.fits


def test_binary_search_needs_few_renders():
    count, calls = pages_with_threshold(9.05)

    fit_font_size(count, min_size=8, max_size=12, step=0.1)

    assert len(calls) <= 8
    assert len(calls) == len(set(calls))


def test_reports_when_even_the_minimum_does_not_fit():
    count, _ = pages_with_threshold(5)

    result = fit_font_size(count, min_size=8, max_size=12)

    assert (result.font_size, result.fits, result.pages) == (8, False, 2)


def test_respects_more_than_one_page():
    result = fit_font_size(lambda size: 2 if size > 9 else 1, max_pages=2)

    assert result.font_size == 12


def test_never_exceeds_max_size_when_the_range_is_not_a_multiple_of_step():
    result = fit_font_size(lambda size: 1, min_size=8, max_size=8.06, step=0.1)

    assert result.font_size == 8


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_pages": 0},
        {"step": 0},
        {"min_size": 12, "max_size": 8},
        {"min_size": 0},
    ],
)
def test_rejects_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        fit_font_size(lambda size: 1, **kwargs)
