"""Deterministic context padding — a plausible dev-session transcript, sized in tokens.

Topics are chosen to be disjoint from every bench domain (no PDFs, commits, AWS,
SQL migrations, Docker, CSV, changelogs, ...) so the padding cannot plausibly
trigger a target skill. Content repeats with seeded variation: for distance
decay, sheer token distance matters, not literary novelty.
"""
import random

_SCENES = [
    # (title, body) — each ~120-180 words with a code fragment, ~200-260 tokens
    ('Chess engine move ordering', '''
We looked at the alpha-beta search next. The engine was exploring 4.2 million
nodes for a depth-9 search, which felt an order of magnitude too high. Killer
moves were being stored but never probed before captures, so the move ordering
was effectively random past the transposition table hit.

    def order_moves(board, moves, killers, depth):
        def score(m):
            if m == tt_move: return 1_000_000
            if board.is_capture(m): return 100_000 + mvv_lva(board, m)
            if m in killers[depth]: return 50_000
            return history[m.from_sq][m.to_sq]
        return sorted(moves, key=score, reverse=True)

After wiring killers ahead of quiet moves the node count dropped to 900k for the
same position set. We also discussed aspiration windows; leaving that for later
since the evaluation function is still material-only plus piece-square tables.
'''),
    ('Thumbnail service memory spike', '''
The image service OOMs when someone uploads a 12000x9000 scan. Resizing streams
through a full decode, so peak memory is width*height*4 bytes regardless of the
target size. The fix was to use the decoder's draft mode to downscale during
decode, then do the final high-quality resample from an already-small bitmap.

    with Image.open(stream) as im:
        im.draft('RGB', (2 * w, 2 * h))
        im = im.convert('RGB')
        im.thumbnail((w, h), Image.LANCZOS)
        im.save(out, 'WEBP', quality=82, method=4)

Peak RSS for the pathological upload went from 1.9GB to 210MB. We agreed to also
reject anything whose header claims more than 80 megapixels before decoding at
all, since draft mode still allocates proportional scratch space in some codecs.
'''),
    ('Weather station firmware drift', '''
The anemometer counts were drifting against the reference station by about 3%
per week. The pulse counter ISR was losing edges while the I2C transaction to
the pressure sensor held the bus, because both shared a critical section. Moving
the pulse accumulation to a hardware timer capture channel fixed the loss.

    void setup_capture(void) {
        TIM2->CCMR1 |= TIM_CCMR1_CC1S_0;   // TI1 input
        TIM2->CCER  |= TIM_CCER_CC1E;      // enable capture
        TIM2->DIER  |= TIM_DIER_CC1IE;     // interrupt on edge
        NVIC_EnableIRQ(TIM2_IRQn);
    }

We still see a fixed 0.4% offset that tracks temperature, which points at the
oscillator rather than lost pulses. A TCXO swap on the next board revision is
cheaper than software compensation tables, so that is the plan of record.
'''),
    ('Pathfinding stutter in the level editor', '''
Dragging a waypoint recomputes flow fields for every agent group each frame,
which is why the editor stutters on the big swamp map. Profiling showed 71% of
the frame in neighbor expansion, almost all of it revisits. The open list was a
plain list with linear extraction instead of a heap.

    while open_heap:
        cost, node = heapq.heappop(open_heap)
        if cost > best[node]:
            continue          # stale entry — the lazy-deletion idiom
        for nxt, step in neighbors(node):
            cand = cost + step
            if cand < best.get(nxt, INF):
                best[nxt] = cand
                heapq.heappush(open_heap, (cand, nxt))

With the heap plus lazy deletion the recompute dropped from 41ms to 6ms, and
batching recomputes behind a 100ms debounce hides the rest while dragging.
'''),
    ('Audio filter clicks at buffer boundaries', '''
The lowpass sweep clicks every 512 samples. Classic symptom: coefficients are
recomputed per buffer from the target cutoff, so the transfer function jumps at
boundaries. The biquad needs per-sample coefficient interpolation, or at least
a one-pole smoother on the cutoff parameter running at audio rate.

    for (int i = 0; i < n; ++i) {
        cutoff_z += smoothing * (cutoff_target - cutoff_z);
        update_biquad(&f, cutoff_z, q);
        out[i] = biquad_tick(&f, in[i]);
    }

Recomputing coefficients every sample cost 11% CPU on the small cores, so we
switched to recomputing every 16 samples with linear interpolation of the five
coefficients in between. Clicks are gone and the sweep sounds continuous even
on the slowest supported handset from the compatibility matrix.
'''),
]


def transcript(target_tokens: int, seed: int = 7) -> str:
    """~target_tokens of session transcript (4 chars ≈ 1 token), deterministic."""
    rng = random.Random(seed)
    scenes = list(_SCENES)
    parts, size, session = [], 0, 1
    while size < target_tokens * 4:
        rng.shuffle(scenes)
        for title, body in scenes:
            parts.append(f'--- session note {session}: {title} ---\n{body.strip()}\n')
            session += 1
        size = sum(len(p) for p in parts)
    text = '\n'.join(parts)
    return text[: target_tokens * 4]
