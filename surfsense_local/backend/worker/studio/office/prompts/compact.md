Write one standalone Python script that builds a $label from the sources below, using their facts only.

Author it with the pre-installed `$library` package and the standard library. Design the layout to fit the content; you are not filling a template.
$focus
$skill

The script MUST, at module level:

- assign the finished file's bytes to `output_bytes`;
- assign a short `title` string;
- assign a `summary` string: a faithful Markdown outline of the content, for search.

Build everything in memory: do not read or write files on disk, and do not use the network.

Return only the Python code. No prose before it, no explanation after it.
