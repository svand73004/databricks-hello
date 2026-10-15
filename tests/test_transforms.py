from hello_bundle.transforms import add_greeting


def test_add_greeting_cleans_and_titlecases():
    result = add_greeting([{"name": "  ada lovelace "}])
    assert result == [{"name": "  ada lovelace ", "greeting": "Hello, Ada Lovelace!"}]


def test_add_greeting_empty():
    assert add_greeting([]) == []
