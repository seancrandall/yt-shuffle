from youtube_mixer.playlist import Video, search, shuffle


def _vids(n: int) -> list[Video]:
    return [Video(id=str(i), title=f"Video {i}") for i in range(n)]


def test_shuffle_preserves_length_and_elements():
    v = _vids(50)
    s = shuffle(v)
    assert len(s) == 50
    assert {x.id for x in s} == {x.id for x in v}


def test_shuffle_has_no_repeats():
    s = shuffle(_vids(50))
    assert len({x.id for x in s}) == 50


def test_shuffle_seed_is_reproducible():
    v = _vids(50)
    assert shuffle(v, seed=1) == shuffle(v, seed=1)


def test_shuffle_does_not_mutate_input():
    v = _vids(20)
    original = [x.id for x in v]
    shuffle(v)
    assert [x.id for x in v] == original


def test_shuffle_changes_order_for_large_list():
    v = _vids(100)
    assert [x.id for x in shuffle(v, seed=7)] != [x.id for x in v]


def test_shuffle_empty_and_single():
    assert shuffle([]) == []
    assert shuffle([Video(id="x", title="t")]) == [Video(id="x", title="t")]


def test_search_filters_case_insensitively():
    v = [
        Video(id="1", title="Cat Video"),
        Video(id="2", title="Dog Video"),
        Video(id="3", title="Catamaran Trip"),
    ]
    assert {x.id for x in search(v, "cat")} == {"1", "3"}


def test_search_empty_query_returns_all():
    v = [Video(id="1", title="A"), Video(id="2", title="B")]
    assert [x.id for x in search(v, "")] == ["1", "2"]
    assert [x.id for x in search(v, "   ")] == ["1", "2"]
