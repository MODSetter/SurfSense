Write one standalone Python script that builds a $label from the sources below with the pre-installed `$library` package. The reader opens the file cold and will never see the sources.
$focus
How to work the material:

- The sources are raw material, not an outline to walk. Decide what the document is for and let its structure follow. A section per source is the failure mode.
- Design the document as one system: a single type scale, one accent, consistent spacing. Restraint reads as competence.
- Prefer the specific figure, date or name over the general statement. Where sources disagree, say so.
- Put only facts the sources state into the document: no outside knowledge, no invented precision, never a placeholder.

The contract:

- The first line is a comment naming the document: `# title: <a short title>`.
- The script runs once, unattended, alone in an empty folder, for at most 120 seconds. It cannot read the sources: write the content into the script.
- Save the file at the path in the `OUTPUT_PATH` environment variable.
- Use only the standard library, $library, matplotlib, Pillow and numpy. No network.
- Draw a chart with matplotlib: save it as a PNG in the working folder, close the figure, then place it scaled to the text width.

$figures

$rules

Return only the Python code. No prose before it, no explanation after it.
