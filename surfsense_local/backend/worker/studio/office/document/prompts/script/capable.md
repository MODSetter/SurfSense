Write one standalone Python script that builds a $label from the sources below, using their facts only, with the pre-installed `$library` package. Design the layout to fit the content; you are not filling a template.
$focus
Work in this order:

1. Read every source and note the figures, dates, names and decisions it states.
2. Decide the document: its sections, their order, and which facts go in each.
3. Write the script that builds exactly that document, following the rules below.
4. Read the script back and check it runs: every name imported, every value defined before use.

The contract:

- The first line is a comment naming the document: `# title: <a short title>`.
- The script runs alone, from an empty folder, for at most 120 seconds. It cannot read the sources: write the content into the script.
- Save the file at the path in the `OUTPUT_PATH` environment variable.
- Use only the standard library, $library, matplotlib, Pillow and numpy. No network.
- Draw a chart with matplotlib only from numbers the sources state: save it as a PNG in the working folder, close the figure, then place the PNG scaled to the text width.

$figures

$rules

Grounding rules:

- Put only facts the sources state into the document. No outside knowledge, no estimates, no placeholder text such as "Lorem ipsum" or "TBD".
- If a source calls something proposed, pending or a draft, label it that way.

Return only the Python code. No prose before it, no explanation after it.
