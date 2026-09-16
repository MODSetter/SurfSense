Write one standalone Python script that builds a $label from the sources below, using their facts only.

Author it with the pre-installed `$library` package and the standard library. Design the layout to fit the content; you are not filling a template.
$focus
Work in this order:

1. Read every source and note the figures, dates, names and decisions it states.
2. Decide the document: its sections, their order, and which facts go in each. Prefer the specific figure over the general statement.
3. Write the script that builds exactly that document, following the authoring rules below.
4. Read the script back and check it runs: every name imported, every value defined before use, no file or network access, and the three module-level assignments present.

Grounding rules:

- Put only facts the sources state into the document. No outside knowledge, no estimates, no placeholder text such as "Lorem ipsum" or "TBD".
- If a source calls something proposed, pending or a draft, label it that way in the document.

$skill

The script MUST, at module level:

- assign the finished file's bytes to `output_bytes`;
- assign a short `title` string;
- assign a `summary` string: a faithful Markdown outline of the content, for search.

Build everything in memory: do not read or write files on disk, and do not use the network.

Return only the Python code. No prose before it, no explanation after it, no markdown fence around it.
