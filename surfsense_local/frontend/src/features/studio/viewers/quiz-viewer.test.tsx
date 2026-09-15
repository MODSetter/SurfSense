import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it } from "vitest"

import { QuizViewer, type Quiz } from "./quiz-viewer"

const quiz: Quiz = {
  schema_version: 1,
  title: "Cassini",
  questions: [
    {
      question_text: "Arrival at Saturn?",
      options: ["1997", "2004", "2010", "2017"],
      correct_option_index: 1,
      explanation_text: "Cassini reached Saturn in July 2004.",
    },
    {
      question_text: "Mission end?",
      options: ["2004", "2010", "2017", "2020"],
      correct_option_index: 2,
      explanation_text: "The Grand Finale plunge was in September 2017.",
    },
  ],
}

afterEach(cleanup)

describe("quiz viewer", () => {
  it("scores each answer with its explanation, then offers to retake the missed ones", async () => {
    const user = userEvent.setup()
    render(<QuizViewer quiz={quiz} />)

    expect(screen.getByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.getByText("Question 1 of 2")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: "1997" }))
    expect(screen.getByText("Incorrect")).toBeTruthy()
    expect(
      screen.getByText("Cassini reached Saturn in July 2004.")
    ).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Next question" }))

    await user.click(screen.getByRole("button", { name: "2017" }))
    expect(screen.getByText("Correct")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "See results" }))

    expect(screen.getByText("1 / 2 correct")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Retake 1 missed" }))
    expect(screen.getByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.getByText("Question 1 of 1")).toBeTruthy()
  })
})
