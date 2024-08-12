import { sum } from "../sum";

test("1 + 1 = 2", () => {
  expect(sum(1, 1)).toBe(2);
});

test("1 + 2 != 2", () => {
  expect(sum(1, 2)).not.toBe(2);
});
