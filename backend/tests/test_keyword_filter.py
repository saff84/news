from app.parsers.keyword_filter import explain_filter, merge_filter_settings, should_keep_item


def test_exclude_substring():
    assert should_keep_item("Новая акция в Москве", {"exclude_keywords": ["акция"]}) is False
    assert should_keep_item("Новая программа", {"exclude_keywords": ["акция"]}) is True


def test_global_merge_exclude():
    merged = merge_filter_settings(
        {"exclude_keywords": ["локально"]},
        {"global_exclude_keywords": ["реклама"]},
    )
    assert should_keep_item("текст реклама", merged) is False
    assert should_keep_item("только локально", merged) is False
    assert should_keep_item("чистый текст", merged) is True


def test_include_requires_match():
    assert should_keep_item("расширение сдано", {"include_keywords": ["расширение"]}) is True
    assert should_keep_item("другая тема", {"include_keywords": ["расширение"]}) is False


def test_whole_words():
    cfg = {"exclude_keywords": ["ак"], "match_whole_words": True}
    assert should_keep_item("акция", cfg) is True
    assert should_keep_item("это ак тест", cfg) is False


def test_explain_exclude():
    r = explain_filter("вакансия менеджер", {"exclude_keywords": ["вакансия"]})
    assert r["keep"] is False
    assert r["reason"] == "exclude"
    assert "вакансия" in r["matched_keywords"]
