def order_slots(entries, pinned, mode):
    """Stable order of (path, trusted activity) views; never filters entries."""
    ranks = {path: i for i, path in reversed(list(enumerate(pinned)))}
    return sorted(entries, key=lambda e: (
        0 if e[0] in ranks else 1,
        ranks[e[0]] if e[0] in ranks else (-e[1] if mode == 'activity' else 0)))
