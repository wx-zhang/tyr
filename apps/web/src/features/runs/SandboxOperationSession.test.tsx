import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SandboxOperationSession } from "./SandboxOperationSession";
import type { components } from "../../api/generated";
type Preview = components["schemas"]["SandboxOperationPreview"];

const preview: Preview = {
  operationId: "operation-1",
  owner: "evidence-and-content",
  state: "execution_completed",
  generation: 1,
  attempts: [
    {
      attempt: 1,
      generation: 1,
      state: "completed",
      programSha256: "a".repeat(64),
      source: { state: "captured", value: "print('encrypted')" },
      execution: {
        exitCode: 0,
        elapsedSeconds: 0.2,
        timedOut: false,
        outputLimited: false,
        stdout: { state: "captured", value: "encrypted" },
        stderr: { state: "empty" },
      },
      outputCount: 1,
    },
  ],
};

describe("SandboxOperationSession", () => {
  it.each([
    "requested",
    "ready",
    "execution_started",
    "collection_started",
    "closing",
    "completed",
    "failed",
    "cancelled",
  ] as const)("renders the %s lifecycle state", (state) => {
    render(<SandboxOperationSession preview={{ ...preview, state }} />);
    const terminal = ["completed", "failed", "cancelled"].includes(state);
    const stateLabel = state
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toUpperCase());
    expect(
      screen.getByRole("status", {
        name: `${terminal ? "" : "Active: "}${stateLabel}`,
      }),
    ).toBeInTheDocument();
  });

  it("renders an accessible live terminal preview with highlighted source", () => {
    render(<SandboxOperationSession preview={preview} />);

    expect(
      screen.getByRole("region", { name: "Sandbox operation preview" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("status", { name: "Active: Execution Completed" }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Python source for sandbox attempt 1"),
    ).toHaveTextContent("print('encrypted')");
    expect(screen.getByText("encrypted")).toBeInTheDocument();
    expect(screen.getByText("Collected 1 output files.")).toBeInTheDocument();
  });

  it("announces initialization and active state without requiring code output", () => {
    render(
      <SandboxOperationSession
        preview={{ ...preview, state: "ready", attempts: [] }}
      />,
    );

    expect(
      screen.getByRole("status", { name: "Active: Ready" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Sandbox is initializing. No code has run yet."),
    ).toBeInTheDocument();
  });

  it("keeps multiple generations bounded and does not render suppressed secrets", () => {
    const secondAttempt = {
      ...preview.attempts![0],
      attempt: 2,
      generation: 2,
      state: "failed" as const,
      source: { state: "suppressed" as const },
      execution: {
        ...preview.attempts![0].execution!,
        stdout: { state: "suppressed" as const },
      },
      failureCode: "timeout",
    };
    render(
      <SandboxOperationSession
        preview={{
          ...preview,
          generation: 2,
          attempts: [preview.attempts![0], secondAttempt],
        }}
      />,
    );
    expect(screen.getByText("Generation 2")).toBeInTheDocument();
    expect(screen.getByText("Attempt 2")).toBeInTheDocument();
    expect(screen.queryByText("secret-value")).not.toBeInTheDocument();
    expect(screen.getAllByText("Suppressed")).toHaveLength(1);
  });

  it("renders output artifacts and opens artifact preview modal when clicked", () => {
    const previewWithOutputs: Preview = {
      ...preview,
      attempts: [
        {
          ...preview.attempts![0],
          outputFiles: [
            {
              path: "upload-001/decoded.txt",
              size: 24,
              sha256: "b".repeat(64),
              contentType: "text/plain",
              content: { state: "captured", value: "Decoded secret content" },
            },
          ],
        },
      ],
    };

    render(<SandboxOperationSession preview={previewWithOutputs} />);

    expect(screen.getByText("Output artifacts (1)")).toBeInTheDocument();
    expect(screen.getByText("upload-001/decoded.txt")).toBeInTheDocument();
    expect(screen.getByText(/text\/plain/)).toBeInTheDocument();

    const previewBtn = screen.getByRole("button", {
      name: "Preview upload-001/decoded.txt",
    });
    expect(previewBtn).toBeInTheDocument();

    // Open modal
    fireEvent.click(previewBtn);
    expect(
      screen.getByRole("dialog", {
        name: "Preview upload-001/decoded.txt",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Decoded secret content")).toBeInTheDocument();

    // Close modal
    fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
    expect(
      screen.queryByRole("dialog", {
        name: "Preview upload-001/decoded.txt",
      }),
    ).not.toBeInTheDocument();
  });
});
