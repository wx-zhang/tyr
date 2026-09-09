import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { CollectorArtifactUpdate } from "./CollectorArtifacts";

const artifacts = [
  {
    scenarioId: "scenario-1",
    scenarioExecutionId: "execution-1",
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

it("keeps keyboard focus contained and closes with Escape before headers arrive", async () => {
  let signal: AbortSignal | null | undefined;
  let finishPreview!: (response: Response) => void;
  vi.mocked(fetch).mockImplementation((_input, init) => {
    signal = init?.signal;
    return new Promise<Response>((resolve) => {
      finishPreview = resolve;
    });
  });
  render(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );
  const opener = screen.getByRole("button", { name: "Preview evidence.md" });
  fireEvent.click(opener);
  const close = screen.getByRole("button", { name: "Close preview" });
  expect(close).toHaveFocus();
  fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
  expect(screen.getByRole("link", { name: "Download original" })).toHaveFocus();
  fireEvent.keyDown(document, { key: "Tab" });
  expect(close).toHaveFocus();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(signal?.aborted).toBe(true);
  await waitFor(() => expect(opener).toHaveFocus());
  await act(async () => {
    finishPreview(new Response("Late evidence"));
  });
  expect(screen.queryByText("Late evidence")).toBeNull();
});

it("does not let an abandoned text body replace a reopened preview", async () => {
  let finishBody!: (body: string) => void;
  const pendingBody = new Promise<string>((resolve) => {
    finishBody = resolve;
  });
  const readBody = vi.fn(() => pendingBody);
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    text: readBody,
  } as unknown as Response);
  render(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview evidence.md" }));
  await waitFor(() => expect(readBody).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Preview evidence.md" }),
    ).toHaveFocus(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview evidence.md" }));
  expect(await screen.findByText("Preview body")).toBeVisible();
  await act(async () => {
    finishBody("Obsolete evidence");
  });
  expect(screen.queryByText("Obsolete evidence")).toBeNull();
  expect(screen.getByText("Preview body")).toBeVisible();
});

it("does not create an object URL after closing during an image body download", async () => {
  let finishBody!: (body: Blob) => void;
  const pendingBody = new Promise<Blob>((resolve) => {
    finishBody = resolve;
  });
  const readBody = vi.fn(() => pendingBody);
  vi.mocked(fetch).mockResolvedValueOnce({
    ok: true,
    blob: readBody,
  } as unknown as Response);
  const artifact = {
    ...artifacts[0],
    files: [
      {
        ...artifacts[0].files[0],
        filename: "evidence.png",
        contentType: "image/png",
      },
    ],
  };
  render(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={artifact} />
    </ol>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview evidence.png" }));
  await waitFor(() => expect(readBody).toHaveBeenCalled());
  fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
  await act(async () => {
    finishBody(new Blob(["image"], { type: "image/png" }));
  });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});

it("replaces preview progress with an error without trapping the operator", async () => {
  let finishPreview!: (response: Response) => void;
  vi.mocked(fetch).mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        finishPreview = resolve;
      }),
  );
  render(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview evidence.md" }));
  expect(screen.getByRole("status")).toBeVisible();
  await act(async () => {
    finishPreview(new Response(null, { status: 503 }));
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Preview failed: 503",
  );
  expect(screen.queryByRole("status")).toBeNull();
  expect(screen.getByRole("link", { name: "Download original" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close preview" }));
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("preserves focus inside a pending preview when collector metadata refreshes", () => {
  vi.mocked(fetch).mockImplementation(() => new Promise<Response>(() => {}));
  const { rerender } = render(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={artifacts[0]} />
    </ol>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview evidence.md" }));
  const download = screen.getByRole("link", { name: "Download original" });
  download.focus();
  rerender(
    <ol>
      <CollectorArtifactUpdate runId="run-1" artifact={{ ...artifacts[0] }} />
    </ol>,
  );
  expect(download).toHaveFocus();
  expect(
    screen.getByRole("status", { name: "Loading preview for evidence.md…" }),
  ).toBeVisible();
});
