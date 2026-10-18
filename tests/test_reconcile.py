from scripts.reconcile_soundtracks import norm, merge_local_tracks


def test_normalization_ignores_punctuation_and_case():
    assert norm('Vettaiyan - Original Soundtrack') == norm('vettaiyan original soundtrack')


def test_new_tracks_default_add_collection_to_false():
    tracks = merge_local_tracks([], [{'filename': '01 - Song A.m4a'}])
    assert tracks[0]['title'] == '01 - Song A'
    assert tracks[0]['add_collection'] is False


def test_existing_track_flag_is_preserved_and_missing_flag_defaults_false():
    existing = [
        {'number': 1, 'title': 'Song A', 'add_collection': True},
        {'number': 2, 'title': 'Song B'},
    ]
    local = [{'filename': 'Song A.flac'}, {'filename': 'Song B.m4a'}, {'filename': 'Song C.m4a'}]
    tracks = merge_local_tracks(existing, local)
    by_title = {track['title']: track for track in tracks}
    assert by_title['Song A']['add_collection'] is True
    assert by_title['Song B']['add_collection'] is False
    assert by_title['Song C']['add_collection'] is False
    assert len(tracks) == 3
