from __future__ import annotations

from core.local_agreement import LocalAgreement, common_prefix_len, normalize_word


def test_normalize_word_ignores_case_punctuation_and_accents():
    assert normalize_word("¿Qué?") == normalize_word("que") == "que"
    assert normalize_word("Año,") == normalize_word("ano")


def test_common_prefix_len_compares_normalized_words():
    assert common_prefix_len(["Hola,", "cómo", "estás"], ["hola", "cómo", "vas"]) == 2
    assert common_prefix_len([], ["hola"]) == 0


def test_update_commits_what_two_hypotheses_agree_on():
    agreement = LocalAgreement()
    committed, provisional = agreement.update(["hola", "como"])
    assert committed == []
    assert provisional == ["hola", "como"]

    committed, provisional = agreement.update(["hola", "cómo", "estás"])
    # Se confirma la forma de la hipótesis más reciente.
    assert committed == ["hola", "cómo"]
    assert provisional == ["estás"]

    committed, provisional = agreement.update(["hola", "cómo", "estás", "tú"])
    assert committed == ["estás"]
    assert provisional == ["tú"]


def test_committed_words_never_go_back():
    agreement = LocalAgreement()
    agreement.update(["buenos", "días"])
    agreement.update(["buenos", "días", "a"])
    committed, provisional = agreement.update(["buenas", "tardes", "a", "todos"])
    assert committed == []
    assert agreement.committed == ["buenos", "días"]
    assert provisional == ["a", "todos"]


def test_finish_returns_full_phrase_and_resets():
    agreement = LocalAgreement()
    agreement.update(["la", "llamada"])
    agreement.update(["la", "llamada", "empezó"])
    assert agreement.finish(["la", "llamada", "empezó", "tarde."]) == [
        "la",
        "llamada",
        "empezó",
        "tarde.",
    ]
    assert agreement.committed == []
    assert agreement.update(["otra"]) == ([], ["otra"])
