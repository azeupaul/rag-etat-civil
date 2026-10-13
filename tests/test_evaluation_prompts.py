from rag_etat_civil.answering.prompt import SYSTEM_PROMPT
from rag_etat_civil.evaluation.prompts import BASELINE_SYSTEM_PROMPT, PROMPTS


def test_the_prompts_to_compare_are_the_current_one_and_the_baseline():
    assert PROMPTS == {"current": SYSTEM_PROMPT, "baseline": BASELINE_SYSTEM_PROMPT}


def test_the_baseline_is_the_prompt_without_the_completeness_rule():
    assert "quelques phrases" in BASELINE_SYSTEM_PROMPT
    assert "Sois complet" not in BASELINE_SYSTEM_PROMPT
    assert "Sois complet" in SYSTEM_PROMPT


def test_both_prompts_keep_the_safety_rules():
    for prompt in PROMPTS.values():
        assert "uniquement à partir des passages" in prompt
        assert 'statut "refused"' in prompt
        assert "ignore-les" in prompt
