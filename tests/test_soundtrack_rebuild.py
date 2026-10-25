from cinescrapper.reconcile_soundtracks import rebuild_tracks


def test_rebuild_uses_current_local_tracks_and_preserves_flags_for_same_path():
    existing = [
        {"fileName": "old-name.m4a", "relative_path": "Movie/old-name.m4a", "add_collection": True},
        {"fileName": "removed.m4a", "relative_path": "Movie/removed.m4a", "add_collection": True},
    ]
    local = [
        {"fileName": "renamed.m4a", "relative_path": "Movie/renamed.m4a", "add_collection": False},
        {"fileName": "old-name.m4a", "relative_path": "Movie/old-name.m4a", "add_collection": False},
    ]

    rebuilt, added, removed = rebuild_tracks(existing, local)

    assert rebuilt == [
        {"fileName": "renamed.m4a", "relative_path": "Movie/renamed.m4a", "add_collection": False},
        {"fileName": "old-name.m4a", "relative_path": "Movie/old-name.m4a", "add_collection": True},
    ]
    assert [track["fileName"] for track in added] == ["renamed.m4a"]
    assert [track["fileName"] for track in removed] == ["removed.m4a"]


def test_rebuild_empty_local_list_removes_all_existing_tracks():
    existing = [{"fileName": "song.flac", "relative_path": "Movie/song.flac", "add_collection": True}]
    rebuilt, added, removed = rebuild_tracks(existing, [])
    assert rebuilt == []
    assert added == []
    assert removed == existing
