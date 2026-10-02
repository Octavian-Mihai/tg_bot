import { expect, it } from "vitest";
import { positionAt } from "./position";

it("empty column", () => expect(positionAt([], 0)).toBe(1));
it("top", () => expect(positionAt([5, 6], 0)).toBe(4));
it("bottom", () => expect(positionAt([5, 6], 2)).toBe(7));
it("middle", () => expect(positionAt([5, 6], 1)).toBe(5.5));
