Write one standalone Python script that builds a $label from the sources below. The reader opens the file cold and will never see the sources.

Author it with the pre-installed `$library` package and the standard library. Design the layout to fit the content; you are not filling a template.
$focus
How to work the material:

- The sources are raw material, not an outline to walk. Read all of them, then decide what the document is for and let its structure follow from that. A section per source is the failure mode.
- Design the document as one system: a single type scale, one accent, consistent spacing, alignment that holds down the page. Restraint reads as competence; decoration reads as filler.
- Prefer the specific figure, date or name over the general statement. Where two sources disagree, or one corrects another, say so in the document rather than choosing silently.
- Distinguish what is settled from what is proposed, pending or conditional.
- Put only facts the sources state into the document. No outside knowledge, no invented precision, and never a placeholder: no "Lorem ipsum", no "TBD", no sample rows.
- Write the script defensively — it runs once, unattended, with no chance to fix an exception: import what you use, define before use, and touch neither disk nor network.
- You tend to converge on generic, on-distribution documents. Resist it — build the one this material asks for.

$skill

The script MUST, at module level:

- assign the finished file's bytes to `output_bytes`;
- assign a short `title` string;
- assign a `summary` string: a faithful Markdown outline of the content, for search.

Return only the Python code. No prose before it, no explanation after it, no markdown fence around it.
