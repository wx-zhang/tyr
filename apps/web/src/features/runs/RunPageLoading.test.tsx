import { QueryClient } from "@tanstack/react-query";
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  renderRunPage,
  setupRunMocks,
  turnsFixture,
  visualizationFixture,
} from "./runPageTestUtils";

const collectorArtifact = {
  scenarioId: "case-alpha",
  scenarioExecutionId: "case-alpha",
  requirement: "file",
  status: "verified",
  requestIds: ["collector-request"],
  verifiedAt: "2026-08-08T10:03:00Z",
  files: [
    {
      fileId: "evidence-1",
      filename: "evidence.txt",
      contentType: "text/plain",
      size: 8,
      sha256: "a".repeat(64),
      downloadAvailable: true,
    },
  ],
};

beforeEach(() => {
  window.localStorage.clear();
  setupRunMocks();
});

it("identifies each pending resource and reveals activity before collector evidence arrives", async () => {
  const originalFetch = vi.mocked(fetch).getMockImplementation()!;
  let finishSummary!: (response: Response) => void;
  let finishActivity!: (response: Response) => void;
  let finishCollector!: (response: Response) => void;
  const summary = new Promise<Response>((resolve) => {
    finishSummary = resolve;
  });
  const activity = new Promise<Response>((resolve) => {
    finishActivity = resolve;
  });
  const collector = new Promise<Response>((resolve) => {
    finishCollector = resolve;
  });
  vi.mocked(fetch).mockImplementation((input, init) => {
    const url = String(input);
    if (url.endsWith("/visualization")) return summary;
    if (url.includes("/turns?")) return activity;
    if (url.endsWith("/collector-verifications")) return collector;
    return originalFetch(input, init);
  });
  renderRunPage();
  expect(
    screen.getByRole("status", { name: "Loading Experiment summary…" }),
  ).toBeVisible();
  expect(
    screen.getByRole("status", { name: "Loading activity…" }),
  ).toBeVisible();
  expect(
    screen.getByRole("status", { name: "Loading collector evidence…" }),
  ).toBeVisible();

  await act(async () => {
    finishSummary(new Response(JSON.stringify(visualizationFixture)));
  });
  expect(
    await screen.findByRole("button", { name: /case-alpha/ }),
  ).toBeVisible();
  await waitFor(() =>
    expect(
      screen.queryByRole("status", { name: "Loading Experiment summary…" }),
    ).toBeNull(),
  );
  expect(
    screen.getByRole("status", { name: "Loading activity…" }),
  ).toBeVisible();

  await act(async () => {
    finishActivity(new Response(JSON.stringify(turnsFixture)));
  });
  await waitFor(() =>
    expect(
      screen.queryByRole("status", { name: "Loading activity…" }),
    ).toBeNull(),
  );
  fireEvent.click(screen.getByRole("button", { name: /case-alpha/ }));
  expect(
    await screen.findByText("read_file", { selector: "code" }),
  ).toBeVisible();
  expect(
    screen.getByRole("status", { name: "Loading collector evidence…" }),
  ).toBeVisible();

  await act(async () => {
    finishCollector(new Response(JSON.stringify([collectorArtifact])));
  });
  expect(
    await screen.findByRole("button", { name: "Preview evidence.txt" }),
  ).toBeVisible();
  expect(
    screen.queryByRole("status", { name: "Loading collector evidence…" }),
  ).toBeNull();
});

it("explains a collector failure and can retry without hiding loaded activity", async () => {
  const originalFetch = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) =>
    String(input).endsWith("/collector-verifications")
      ? Promise.resolve(new Response(null, { status: 503 }))
      : originalFetch(input, init),
  );
  renderRunPage();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not load collector evidence",
  );
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  expect(
    await screen.findByText("read_file", { selector: "code" }),
  ).toBeVisible();

  let finishCollector!: (response: Response) => void;
  const collector = new Promise<Response>((resolve) => {
    finishCollector = resolve;
  });
  vi.mocked(fetch).mockImplementation((input, init) =>
    String(input).endsWith("/collector-verifications")
      ? collector
      : originalFetch(input, init),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Retry collector evidence" }),
  );
  expect(
    await screen.findByRole("status", { name: "Loading collector evidence…" }),
  ).toBeVisible();
  expect(screen.getByText("read_file", { selector: "code" })).toBeVisible();
  await act(async () => {
    finishCollector(new Response(JSON.stringify([collectorArtifact])));
  });
  expect(
    await screen.findByRole("button", { name: "Preview evidence.txt" }),
  ).toBeVisible();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("retains loaded summary, activity and collector evidence during a slow refresh", async () => {
  const originalFetch = vi.mocked(fetch).getMockImplementation()!;
  vi.mocked(fetch).mockImplementation((input, init) =>
    String(input).endsWith("/collector-verifications")
      ? Promise.resolve(new Response(JSON.stringify([collectorArtifact])))
      : originalFetch(input, init),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  renderRunPage(queryClient);
  fireEvent.click(await screen.findByRole("button", { name: /case-alpha/ }));
  expect(
    await screen.findByRole("button", { name: "Preview evidence.txt" }),
  ).toBeVisible();
  expect(screen.getByText("read_file", { selector: "code" })).toBeVisible();

  let finishRefresh!: (response: Response) => void;
  const refresh = new Promise<Response>((resolve) => {
    finishRefresh = resolve;
  });
  vi.mocked(fetch).mockImplementation(() => refresh);
  act(() => {
    void queryClient.invalidateQueries();
  });
  expect(
    screen.getByRole("button", { name: "Preview evidence.txt" }),
  ).toBeVisible();
  expect(screen.getByText("read_file", { selector: "code" })).toBeVisible();
  expect(
    screen.queryByRole("status", {
      name: /^Loading (Experiment summary|activity|collector evidence)/,
    }),
  ).toBeNull();
  await act(async () => {
    finishRefresh(new Response(null, { status: 503 }));
  });
  expect(
    await screen.findByText(/Could not load collector evidence/),
  ).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Preview evidence.txt" }),
  ).toBeVisible();
  expect(screen.getByText("read_file", { selector: "code" })).toBeVisible();
});
