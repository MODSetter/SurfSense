import { cleanup, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { render } from "@/test-utils"
import type { ArtifactDetail, QuizState } from "../../api"
import { QuizViewer } from "./quiz-viewer"

const quizFile = {
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

const artifact: ArtifactDetail = {
  id: 1,
  document_id: 1,
  format: "quiz",
  generation: 1,
  title: "Cassini",
  status: "ready",
  error_message: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  content: null,
  files: [
    {
      role: "primary",
      mime_type: "application/json",
      size_bytes: 200,
      original_filename: "cassini.json",
    },
  ],
  quiz_state: null,
  flashcard_state: null,
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe("quiz viewer", () => {
  it("scores each answer against the server, then retakes the missed ones", async () => {
    // A minimal stand-in for the real quiz-state endpoints (see
    // backend/modules/artifacts/quiz_progress.py), just enough to prove the
    // viewer round-trips through PUT/GET rather than mutating local state.
    let state: QuizState = {
      generation: 1,
      mode: "all",
      active_question_indices: [0, 1],
      answers: {},
      skipped_question_indices: [],
    }

    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input)
        if (url === "/artifacts/1/files/primary") {
          return Response.json(quizFile)
        }
        if (
          url === "/artifacts/1/quiz-state/answer" &&
          init?.method === "PUT"
        ) {
          const body = JSON.parse(init.body as string)
          state = {
            ...state,
            answers: {
              ...state.answers,
              [body.question_index]: body.selected_option_index,
            },
          }
          return Response.json(state)
        }
        if (
          url === "/artifacts/1/quiz-state/retake" &&
          init?.method === "PUT"
        ) {
          const body = JSON.parse(init.body as string)
          state =
            body.mode === "missed"
              ? {
                  generation: 1,
                  mode: "missed",
                  active_question_indices: [0],
                  answers: {},
                  skipped_question_indices: [],
                }
              : {
                  generation: 1,
                  mode: "all",
                  active_question_indices: [0, 1],
                  answers: {},
                  skipped_question_indices: [],
                }
          return Response.json(state)
        }
        throw new Error(`unhandled request: ${url}`)
      })
    )

    const user = userEvent.setup()
    render(<QuizViewer artifact={artifact} />)

    expect(await screen.findByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.getByText("1 / 2")).toBeTruthy()

    await user.click(screen.getByRole("radio", { name: /1997/ }))
    expect(await screen.findByText("Incorrect answer")).toBeTruthy()
    expect(screen.getByText("Correct answer")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Next" }))

    expect(screen.getByText("Mission end?")).toBeTruthy()
    expect(screen.getByText("2 / 2")).toBeTruthy()
    await user.click(screen.getByRole("radio", { name: /2017/ }))
    expect(await screen.findByText("Correct answer")).toBeTruthy()
    await user.click(screen.getByRole("button", { name: "Finish" }))

    expect(screen.getByText("1/2")).toBeTruthy()
    expect(screen.getByText("(50%)")).toBeTruthy()

    await user.click(screen.getByRole("button", { name: /Retake quiz/ }))
    await user.click(
      await screen.findByRole("menuitem", { name: "Retake missed questions" })
    )

    expect(await screen.findByText("Arrival at Saturn?")).toBeTruthy()
    expect(screen.getByText("1 / 1")).toBeTruthy()
  })
})
