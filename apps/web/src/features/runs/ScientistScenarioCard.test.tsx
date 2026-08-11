import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScientistScenarioCard } from "./ScientistScenarioCard";

it("highlights a ready scenario with id and title", () => {
  render(
    <ScientistScenarioCard
      turn={{
        id: "sci-1",
        sequence: 4,
        number: 1,
        stage: "scientist",
        caseId: "http-patch-delivery-approval-gate",
        status: "ready",
        agentMessage: "HTTP PATCH delivery to store tests Tyr approval gate",
        tyrMessage: null,
        occurredAt: "2026-08-11T19:44:22Z",
        repliedAt: null,
      }}
    />,
  );

  expect(screen.getByLabelText("New scientist scenario")).toBeInTheDocument();
  expect(screen.getByText("New scenario")).toBeInTheDocument();
  expect(
    screen.getByText("http-patch-delivery-approval-gate"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("HTTP PATCH delivery to store tests Tyr approval gate"),
  ).toBeInTheDocument();
  expect(screen.getByText("Ready for execution against Tyr.")).toBeInTheDocument();
});

it("shows designing state while generating", () => {
  render(
    <ScientistScenarioCard
      turn={{
        id: "sci-2",
        sequence: 5,
        number: 2,
        stage: "scientist",
        caseId: null,
        status: "generating",
        agentMessage: "Iteration 2 uses 3 prior test(s)",
        tyrMessage: null,
        occurredAt: "2026-08-11T19:45:00Z",
        repliedAt: null,
      }}
    />,
  );

  expect(screen.getByText("Designing")).toBeInTheDocument();
  expect(
    screen.getByText(/Waiting for the model to return a scenario definition/),
  ).toBeInTheDocument();
});
