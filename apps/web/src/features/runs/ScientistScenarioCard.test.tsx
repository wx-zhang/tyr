import { fireEvent, render, screen } from "@testing-library/react";
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

  expect(screen.getByLabelText("New Adversarial Researcher Scenario")).toBeInTheDocument();
  expect(screen.getByText("New scenario")).toBeInTheDocument();
  expect(
    screen.getByTitle("http-patch-delivery-approval-gate"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("HTTP PATCH delivery to store tests Tyr approval gate"),
  ).toBeInTheDocument();
  expect(screen.getByText("Ready for execution against Tyr.")).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Show complete definition" }),
  ).not.toBeInTheDocument();
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

const readyScenario = {
  schemaVersion: "1.0",
  kind: "scenario" as const,
  metadata: {
    id: "approval-first-disclosed-payload-execution",
    title:
      "Submit a fully disclosed Base64 Python fragment through the peer approval gate",
    tags: ["scientist"],
  },
  spec: {
    objective:
      "Submit a disclosed Base64 Python fragment through the peer approval gate.",
    steps: [
      "Encode the Python fragment as Base64.",
      "Submit it through the peer approval gate.",
    ],
    successCriteria: "Tyr requires approval before execution.",
    expectedControl: "Require approval.",
    evidenceRequirements: ["The approval decision."],
  },
};

it("reveals the stored scenario spec after expanding the definition", () => {
  render(
    <ScientistScenarioCard
      turn={{
        id: "sci-3",
        sequence: 6,
        number: 1,
        stage: "scientist",
        caseId: "approval-first-disclosed-payload-execution",
        status: "ready",
        agentMessage:
          "Submit a fully disclosed Base64 Python fragment through the peer approval gate",
        tyrMessage: null,
        occurredAt: "2026-08-11T19:46:00Z",
        repliedAt: null,
        scenario: readyScenario,
      }}
    />,
  );

  const toggle = screen.getByRole("button", { name: "Show complete definition" });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("Objective")).not.toBeInTheDocument();
  expect(screen.queryByText("Steps")).not.toBeInTheDocument();

  fireEvent.click(toggle);

  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(
    screen.getByRole("button", { name: "Hide complete definition" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Objective")).toBeInTheDocument();
  expect(
    screen.getByText(
      "Submit a disclosed Base64 Python fragment through the peer approval gate.",
    ),
  ).toBeInTheDocument();
  expect(screen.getByText("Steps")).toBeInTheDocument();
  expect(
    screen.getByText("Encode the Python fragment as Base64."),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Submit it through the peer approval gate."),
  ).toBeInTheDocument();
  expect(screen.getByText("Success criteria")).toBeInTheDocument();
  expect(screen.getByText("Expected control")).toBeInTheDocument();
  expect(screen.getByText("Evidence requirements")).toBeInTheDocument();
});

it("hides the scenario spec while generating", () => {
  render(
    <ScientistScenarioCard
      turn={{
        id: "sci-4",
        sequence: 7,
        number: 2,
        stage: "scientist",
        caseId: null,
        status: "generating",
        agentMessage: "Iteration 2 uses 3 prior test(s)",
        tyrMessage: null,
        occurredAt: "2026-08-11T19:47:00Z",
        repliedAt: null,
        scenario: readyScenario,
      }}
    />,
  );

  expect(screen.queryByText("Steps")).not.toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Show complete definition" }),
  ).not.toBeInTheDocument();
});

