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

it("defaults refresh rate to 30s and lets the operator change it", async () => {
  window.localStorage.removeItem("gamr-run-refresh-ms");
  renderRunPage();
  const thirty = await screen.findByRole("radio", { name: "30s" });
  expect(thirty).toHaveAttribute("aria-checked", "true");
  expect(thirty).toHaveClass("is-selected");

  const five = screen.getByRole("radio", { name: "5s" });
  fireEvent.click(five);
  expect(five).toHaveAttribute("aria-checked", "true");
  expect(five).toHaveClass("is-selected");
  expect(thirty).toHaveAttribute("aria-checked", "false");
  expect(window.localStorage.getItem("gamr-run-refresh-ms")).toBe("5000");
});
