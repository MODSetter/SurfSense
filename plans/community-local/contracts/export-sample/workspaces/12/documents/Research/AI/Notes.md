---
type: File
title: Notes
timestamp: '2026-05-01T09:00:00+00:00'
---
# Notes

Attention is a weighted average over the value vectors. The weights come from a softmax over query-key dot products, scaled by the square root of the key dimension.

Two things worth remembering:

- Scaling keeps the softmax out of its saturated region for large dimensions.
- Multi-head attention runs several of these in parallel with different projections.
