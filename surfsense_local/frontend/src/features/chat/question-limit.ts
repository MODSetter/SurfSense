// Mirrors QUESTION_CHARS in surfsense_local/backend/modules/chat/budget.py:
// the question's 1,024-token share of the window at four characters a token.
// The wire refuses more with a 422; the composer stops first, so nobody finds
// out on send.
export const QUESTION_MAX_CHARS = 4096
