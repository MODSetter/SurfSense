"""A recording as a source: decoded in a child, cut at its pauses into windows,
each written down through the API, and kept as a timestamped transcript. The
job resumes from its checkpoint after a yield, a retry or a restart."""
