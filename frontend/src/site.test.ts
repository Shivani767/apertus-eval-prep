import { describe, expect, it } from "vitest"
import { fmtDelta, fmtP, fmtPct, shortLabel } from "./data"
import type { SiteData } from "./data"
import site from "./data/site.json"

const S = site as unknown as SiteData

describe("formatters never fabricate", () => {
  it("renders missing numerics as Not measured, not 0", () => {
    expect(fmtPct(null)).toBe("Not measured")
    expect(fmtPct(undefined)).toBe("Not measured")
    expect(fmtPct(0)).toBe("0.00%")
    expect(fmtDelta(null)).toBe("Not measured")
    expect(fmtP(null)).toBe("Not applicable")
    expect(fmtP(0.00001)).toBe("< 0.001")
    expect(fmtP(0.042)).toBe("0.042")
  })
  it("shortens model labels deterministically", () => {
    expect(shortLabel("Qwen/Qwen2.5-3B-Instruct")).toBe("Qwen2.5-3B")
    expect(shortLabel("abc")).toBe("abc")
  })
})

describe("site.json fixture integrity", () => {
  it("coverage is internally consistent", () => {
    expect(S.coverage.measured).toBe(S.coverage.n_cells - S.coverage.pending)
    expect(S.coverage.planned_cells).toBe(34)
    expect(S.cells.length).toBe(S.coverage.n_rows)
  })
  it("every measured cell traces to registry accuracy", () => {
    for (const c of S.cells) {
      if (c.status === "PENDING") expect(c.accuracy).toBeNull()
    }
  })
  it("control-vs-5shot reversal is present and flagged", () => {
    const five = S.ranking_comparisons.find((c) => c.variant_key === "prompt_id=5shot")
    expect(five).toBeDefined()
    expect(five!.reordered).toBe(true)
    expect(five!.variant_order[0]).toContain("Qwen")
  })
  it("ERS is provisional with documented exclusions", () => {
    expect(S.reliability.provisional).toBe(true)
    expect(S.reliability.excluded_models).toContain("Qwen/Qwen2.5-7B-Instruct")
    expect(S.reliability.disclaimer.length).toBeGreaterThan(20)
  })
  it("statistics carry multiple-comparison corrections", () => {
    expect(S.statistics.n_tests_corrected).toBeGreaterThan(0)
    for (const c of S.statistics.comparisons) {
      expect(c.perm_p_holm).not.toBeUndefined()
      expect(c.perm_p_bh).not.toBeUndefined()
    }
  })
  it("reproducibility commands are real CLI invocations", () => {
    const cmds = Object.values(S.reproducibility.commands)
    expect(cmds.length).toBeGreaterThan(0)
    for (const c of cmds) {
      expect(c.sweep_command).toContain("python -m apertus_eval_prep sweep")
    }
  })
})
