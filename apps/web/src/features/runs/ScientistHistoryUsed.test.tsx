import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import {
  buildCaseOriginMap,
  resolveHistoryCases,
  ScientistHistoryUsed,
} from "./ScientistHistoryUsed";

it("groups base and scientist history cases with origin labels", () => {
  render(
    <ScientistHistoryUsed
      cases={[
        { caseId: "base-case", origin: "base" },
        { caseId: "sci-case", origin: "scientist" },
      ]}
    />,
  );

  const panel = screen.getByLabelText("Tests used from history");
  expect(within(panel).getByText("Seed history")).toBeInTheDocument();
  expect(within(panel).getByText(/2 prior tests/)).toBeInTheDocument();
  expect(within(panel).getByLabelText("Base scenarios")).toBeInTheDocument();
  expect(
    within(panel).getByLabelText("Scientist scenarios"),
  ).toBeInTheDocument();
  expect(within(panel).getByText("base-case")).toBeInTheDocument();
  expect(within(panel).getByText("sci-case")).toBeInTheDocument();
  expect(within(panel).getAllByText("Base").length).toBeGreaterThan(0);
  expect(within(panel).getAllByText("Scientist").length).toBeGreaterThan(0);
});

it("shows an empty state when no prior tests exist", () => {
  render(<ScientistHistoryUsed cases={[]} />);
  expect(screen.getByText("No prior tests were available.")).toBeInTheDocument();
});

it("builds origin map from configured base ids and scientist turns", () => {
  const map = buildCaseOriginMap(
    [
      { stage: "case", caseId: "base-a", status: "completed" },
      {
        stage: "scientist",
        caseId: "sci-a",
        status: "ready",
        tyrMessage: null,
      },
    ],
    ["base-a", "base-b"],
  );
  expect(map.get("base-a")).toBe("base");
  expect(map.get("base-b")).toBe("base");
  expect(map.get("sci-a")).toBe("scientist");
});

it("resolves origins from API list, map, then task membership", () => {
  const fromApi = resolveHistoryCases(["a", "b"], {
    origins: ["base", "scientist"],
  });
  expect(fromApi).toEqual([
    { caseId: "a", origin: "base" },
    { caseId: "b", origin: "scientist" },
  ]);

  const fromTask = resolveHistoryCases(
    ["rename-relocate-fresh-agent-upload", "http-patch-delivery"],
    {
      taskCaseIds: ["rename-relocate-fresh-agent-upload"],
    },
  );
  expect(fromTask).toEqual([
    { caseId: "rename-relocate-fresh-agent-upload", origin: "base" },
    { caseId: "http-patch-delivery", origin: "scientist" },
  ]);
});
