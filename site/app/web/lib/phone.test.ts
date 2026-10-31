import { describe, expect, it } from "vitest";
import { formatPhone } from "./phone";

describe("formatPhone", () => {
  it("formats ukrainian numbers", () => expect(formatPhone("380671234501")).toBe("+380 67 123 45 01"));
  it("falls back", () => {
    expect(formatPhone("12345")).toBe("+12345");
    expect(formatPhone("")).toBe("");
  });
});
