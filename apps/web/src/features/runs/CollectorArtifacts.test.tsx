import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CollectorArtifacts } from "./CollectorArtifacts";

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
      return {
        ok: true,
        json: async () => [
          {
            caseId: "case-1",
            requirement: "file",
            status: "verified",
            requestIds: ["0123456789abcdef0123456789abcdef"],
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
        ],
      };
    }),
  );
});

afterEach(() => vi.useRealTimers());

it("shows verified remote-backed files with a run-scoped download", async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CollectorArtifacts runId="run-1" />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("evidence.md")).toBeInTheDocument();
  expect(screen.getByText("Verified")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Download evidence.md" })).toHaveAttribute(
    "href",
    "http://127.0.0.1:6687/api/v1/runs/run-1/collector-files/file-1/download",
  );
});

it("previews markdown in an accessible modal and closes with Escape", async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CollectorArtifacts runId="run-1" />
    </QueryClientProvider>,
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
    return {
      ok: true,
      json: async () => [
        {
          caseId: "case-1",
          requirement: "file",
          status: "verified",
          requestIds: [],
          files: [
            {
              fileId: "image-1",
              filename: "evidence.png",
              contentType: "image/png",
              size: 8,
              sha256: "a".repeat(64),
              downloadAvailable: true,
            },
            {
              fileId: "archive-1",
              filename: "evidence.zip",
              contentType: "application/zip",
              size: 8,
              sha256: "b".repeat(64),
              downloadAvailable: true,
            },
          ],
        },
      ],
    } as Response;
  });
  render(
    <QueryClientProvider client={new QueryClient()}>
      <CollectorArtifacts runId="run-1" />
    </QueryClientProvider>,
  );

  fireEvent.click(await screen.findByRole("button", { name: "Preview evidence.png" }));
  expect(await screen.findByRole("img", { name: "Preview of evidence.png" })).toHaveAttribute(
    "src",
    "blob:preview",
  );
  expect(screen.queryByRole("button", { name: "Preview evidence.zip" })).toBeNull();
});

it("polls for collector artifacts while the run is live", async () => {
  let requests = 0;
  vi.mocked(fetch).mockImplementation(async () => ({
    ok: true,
    json: async () => {
      requests += 1;
      if (requests === 1) return [];
      return [
        {
          caseId: "case-live",
          requirement: "file",
          status: "verified",
          requestIds: [],
          files: [],
        },
      ];
    },
  }) as Response);

  render(
    <QueryClientProvider client={new QueryClient()}>
      <CollectorArtifacts runId="run-live" isLive refreshMs={10} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("case-live")).toBeVisible();
  expect(requests).toBeGreaterThanOrEqual(2);
});
