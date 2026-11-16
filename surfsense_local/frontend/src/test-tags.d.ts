import "vitest"

// Tag names are checked: a misspelled tag is a type error, not a test that never runs.
declare module "vitest" {
  interface TestTags {
    tags: "docker"
  }
}
