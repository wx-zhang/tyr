import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CollectorArtifactUpdate } from "./CollectorArtifacts";

const artifacts = [
  {
    caseId: "case-1",
    requirement: "file",
    status: "verified",
    requestIds: ["0123456789abcdef0123456789abcdef"],
    verifiedAt: "2026-08-12T09:59:57Z",
    files: [
      {
        fileId: "file-1",
        filename: "evidence.md",
        contentType: "text/markdown",
        size: 8,
        sha256: "a".repeat(64),
        downloadAvailable: true,
      },
    ],
  },
];

beforeEach(() => {
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:preview"),
    revokeObjectURL: vi.fn(),
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url = String(input);
      if (url.endsWith("/preview")) {
        return {
          ok: true,
          headers: new Headers({ "content-type": "text/plain" }),
          text: async () => "# Evidence\n\nPreview body",
        };
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );
});

afterEach(() => vi.useRealTimers());

it("shows verified remote-backed files with a run-scoped download", async () => {
  render(
    <ol aria-label="Run updates">
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );

  expect(screen.getByText("evidence.md")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "File received - case-1" }),
  ).toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "Collector artifacts" })).toBeNull();
  expect(screen.getByText("Verified")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download evidence.md" })).toHaveAttribute(
    "href",
    "http://127.0.0.1:6687/api/v1/runs/run-1/collector-files/file-1/download",
  );
});

it("previews markdown in an accessible modal and closes with Escape", async () => {
  render(
    <ol aria-label="Run updates">
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Preview evidence.md" }));
  expect(await screen.findByRole("dialog", { name: "Preview evidence.md" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Evidence" })).toBeVisible();
  expect(screen.getByText("Preview body")).toBeVisible();
  fireEvent.keyDown(document, { key: "Escape" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByRole("button", { name: "Preview evidence.md" })).toHaveFocus();
});

it("shows image previews without rendering unsupported file types", async () => {
  vi.mocked(fetch).mockImplementation(async (input: string | URL | Request) => {
    const url = String(input);
    if (url.endsWith("/preview")) {
      return {
        ok: true,
        headers: new Headers({ "content-type": "image/png" }),
        blob: async () => new Blob(["image"], { type: "image/png" }),
      } as Response;
    }
    throw new Error(`Unexpected request: ${url}`);
  });
  const imageArtifacts = [
    {
      ...artifacts[0],
      files: [
        {
          ...artifacts[0].files[0],
          fileId: "image-1",
          filename: "evidence.png",
          contentType: "image/png",
        },
        {
          ...artifacts[0].files[0],
          fileId: "archive-1",
          filename: "evidence.zip",
          contentType: "application/zip",
        },
      ],
    },
  ];
  render(<ol><CollectorArtifactUpdate runId="run-1" artifact={imageArtifacts[0]} /></ol>);

  fireEvent.click(await screen.findByRole("button", { name: "Preview evidence.png" }));
  expect(await screen.findByRole("img", { name: "Preview of evidence.png" })).toHaveAttribute(
    "src",
    "blob:preview",
  );
  expect(screen.queryByRole("button", { name: "Preview evidence.zip" })).toBeNull();
});

it("offers a text preview for an XML request body", async () => {
  const bodyArtifact = {
    ...artifacts[0],
    requirement: "request",
    files: [
      {
        ...artifacts[0].files[0],
        fileId: "body-0123456789abcdef0123456789abcdef",
        filename: "request-body.xml",
        contentType: "application/xml",
      },
    ],
  };
  render(<ol><CollectorArtifactUpdate runId="run-1" artifact={bodyArtifact} /></ol>);

  expect(
    await screen.findByRole("button", { name: "Preview request-body.xml" }),
  ).toBeVisible();
  expect(screen.getByRole("link", { name: "Download request-body.xml" })).toBeVisible();
});
