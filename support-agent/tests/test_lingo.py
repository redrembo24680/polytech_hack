from agent.lingo import EMOTION_GUIDE, EMOTIONS, GLOSSARY, REGISTER_RULE, render_glossary


def test_glossary_pairs_are_nonempty_strings():
    assert len(GLOSSARY) >= 20
    assert all(isinstance(a, str) and isinstance(b, str) and a.strip() and b.strip() for a, b in GLOSSARY)


def test_render_glossary_contains_sample_pair():
    out = render_glossary()
    assert "відмінити" in out and "скасувати" in out
    assert "{" not in out and "}" not in out


def test_every_emotion_has_guide():
    assert set(EMOTIONS) == set(EMOTION_GUIDE)
    assert all(EMOTION_GUIDE[e].strip() for e in EMOTIONS)
    assert "регістр" in REGISTER_RULE.lower()
