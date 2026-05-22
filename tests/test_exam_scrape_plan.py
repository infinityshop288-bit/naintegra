from naintegra_lex_agent.exam_scrape.targets import EXAM_BOARDS, EXAM_CARGOS
from naintegra_lex_agent.exam_scrape.url_plan import build_full_plan, slice_plan


def test_plan_qconcurso_only_count() -> None:
    plan = build_full_plan(include_official=False, sources=("qconcurso",))
    assert len(plan) == len(EXAM_BOARDS) * len(EXAM_CARGOS)


def test_plan_two_sources_doubles() -> None:
    plan = build_full_plan(include_official=False, sources=("qconcurso", "techconcursos"))
    assert len(plan) == 2 * len(EXAM_BOARDS) * len(EXAM_CARGOS)


def test_slice_plan_rotates() -> None:
    plan = build_full_plan(include_official=False, sources=("qconcurso",))
    a = slice_plan(plan, offset=0, limit=3)
    b = slice_plan(plan, offset=len(plan) - 1, limit=3)
    assert len(a) == 3
    assert len(b) == 3
    assert a[0].url != b[0].url or len(plan) <= 1


def test_nav_tags_include_banca_fonte() -> None:
    plan = build_full_plan(include_official=False, sources=("qconcurso",))
    nav = plan[0]
    assert nav.tags["banca"] in EXAM_BOARDS
    assert nav.tags["fonte"] == "qconcursos.com"
