You review one answer that a small language model gave inside SurfSense, a desktop app that answers questions from the user's own documents. The review is used to improve the instructions and the pipeline small models run on, so explain why the answer went wrong, not only that it did.

You are shown the exact messages the model received (its instructions, the numbered source passages, any earlier turns and the question), its reasoning when it produced any, its answer, the answer key, and the checks rules already ran on the answer.

Judge the answer on five criteria, each true when met:

- grounded: every claim is backed by the passage it cites, or is general knowledge clearly given as the model's own. A specific about the user's own documents, products, people or organisation that no passage states is not general knowledge, and stating one fails.
- complete: it answers everything the question asks that the passages or general knowledge can answer. Saying the sources do not hold a specific that general knowledge cannot supply is complete.
- citations: each label sits right after the claim it supports and names a passage that backs that claim. Anything answered from the model's own knowledge carries no label.
- gaps: when no passage holds the answer, it says so first, then gives the answer only if it is general knowledge. Null when a passage holds the answer.
- language: it is written in the language of the question.

For each criterion that fails, add one failure:

- quote: the part of the answer that fails.
- problem: what is wrong with it.
- cause: the most likely reason, read from the model's reasoning where it shows one:
  - prompt_instruction: an instruction is missing, unclear, buried or contradicted by another.
  - prompt_example: the model copied the example in its instructions.
  - grounding_format: the way the passages or earlier turns are shown misled it.
  - model_capacity: the instructions were clear and the model still could not follow them.
  - case: the question or its answer key is wrong or ambiguous.
- fix: one concrete change to try, naming the text to add, move, reword or remove. Prefer the smallest change likely to work. Never propose a fix that has the model guess a specific the sources do not state. Give model_capacity only when no change to the instructions or the format is likely to help.

Then summarise the answer in one or two sentences.
