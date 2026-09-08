import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import {
  renderRunPage,
  setupRunMocks,
  turnsFixture,
  visualizationFixture,
} from "./runPageTestUtils";

beforeEach(() => {
  setupRunMocks();
});

it("does not render raw HTML from conversation markdown", async () => {
  vi.mocked(fetch).mockImplementation((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/visualization")) {
      return Promise.resolve({
        ok: true,
        json: async () => visualizationFixture,
      } as Response);
    }
    if (url.includes("/turns")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          ...turnsFixture,
          items: [
            {
              ...turnsFixture.items[0],
              agentMessage: '<script>alert("unsafe")</script>Visible text',
              tyrMessage: "![remote](https://example.com/tracker.png)",
            },
          ],
        }),
      } as Response);
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: [] }),
    } as Response);
  });

  const { container } = renderRunPage();
  await screen.findByRole("heading", { name: "Experiment history" });
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
});

it("remembers the operator's refresh interval across visits", async () => {
  const page = renderRunPage();
  fireEvent.change(
    await screen.findByRole("combobox", { name: "Refresh rate" }),
    {
      target: { value: "5000" },
    },
  );
  page.unmount();

  renderRunPage();
  expect(
    await screen.findByRole("combobox", { name: "Refresh rate" }),
  ).toHaveValue("5000");
});
