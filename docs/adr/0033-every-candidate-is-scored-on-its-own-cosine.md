# ADR 0033: Every candidate is scored on its own cosine, because a chunk the vector leg did not reach is unmeasured rather than unrelated

- **Status:** Accepted
- **Date:** 2026-09-24
- **Amends:** [ADR 0031](0031-ranking-blends-absolute-leg-scores.md), whose "a candidate missing from a leg takes nothing from it" is right for the keyword leg and wrong for this one
- **Source:** [retrieval eval](../../surfsense_local/backend/scripts/run_retrieval_eval.py), [ADR 0031](0031-ranking-blends-absolute-leg-scores.md)

## Context

[ADR 0031](0031-ranking-blends-absolute-leg-scores.md) has each leg propose candidates and blends the union, a candidate missing from a leg taking nothing from it. For the keyword leg that is exactly right: absent means the chunk matched none of the query's terms, which is a measurement, and zero is what it measured.

The vector leg is different. It returns the nearest `CANDIDATES` chunks and nothing else, so absent means *not among the nearest twenty* — a fact about the other nineteen, not about this chunk. Scored as zero it reads as "means nothing", which is the strongest claim the leg can make about a chunk it never looked at.

Nothing in the eval showed this while bge-small was the only embedder. It surfaced when [granite-embedding-97m-multilingual-r2](../architecture/search.md) was spiked for the cross-lingual gap: LIMIT-small fell from 100% to 74%, and no `SEMANTIC_WEIGHT` recovered both slices. In all 52 lost queries the answering chunk carried nearly double the winning chunk's term coverage (0.696 against 0.364) and scored cosine 0.000. Its real cosine was 0.757. The leg had not judged it badly; it had not judged it.

The number was already there: `_best` computes `vec_distance_cosine` for every fused candidate in order to return `Hit.score`, one function after the blend discarded it.

## Decision

- **The vector leg proposes candidates and does not score them.** It returns chunk ids; the blend reads the exact cosine `_best` already measures for the whole union. The keyword leg still both proposes and scores, because its absence is a measurement.
- Cosine still floors at zero, and `SEMANTIC_WEIGHT` is unchanged at 0.65.
- Rejected: **widening `k`**. With a corpus smaller than `k` it converges on this decision anyway, and it pays for distance on chunks the blend will not rank, where scoring the union is already paid for.
- Rejected for now: **subtracting a cosine floor**. Cosine does not reach zero on real text — over unrelated passages it bottoms out near 0.62 for bge-small and 0.75 for granite — so the semantic leg never truly abstains, and rescaling from a floor is what makes granite hold both slices at once (cross-lingual 88%, LIMIT 100%). A single constant does not survive the change of scale: 0.65 is right for the eval's documents and wrong for a corpus of one-line notes, where it zeroes a correct match. It belongs with the embedder swap, derived rather than fixed.

## Consequences

- bge-small is unchanged on every slice of the eval: 98% of 266 queries, LIMIT-small 100%, cross-lingual 25%. Seven queries move rank, four up and two down by one place. The mean rank when found reads 1.1 → 1.2 because one cross-lingual answer that was previously never returned now comes back at rank 10; the average rises by gaining an answer, not by losing a position.
- A crowded workspace can no longer reorder a quiet one. KNN takes the global nearest before the workspace filter runs, so a neighbour holding twenty closer chunks used to leave every one of your own notes unscored and hand the order to whichever chunk carried more of the query's words.
- The vector leg can still starve a workspace of *candidates*, which this does not fix: a chunk in neither leg is never ranked. Filtering the workspace inside the KNN is the fix, tracked as a known gap in [search](../architecture/search.md).
- `_fuse` is gone. Blending happens where the cosine is measured, which is the only place both numbers exist.
- No index or vector changes, so no migration and no re-embed.
