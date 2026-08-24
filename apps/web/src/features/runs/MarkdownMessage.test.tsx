import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExpandableMarkdownMessage, MarkdownMessage } from "./MarkdownMessage";

describe("MarkdownMessage", () => {
  it("renders short markdown content directly", () => {
    render(<MarkdownMessage content="Short text" />);
    expect(screen.getByText("Short text")).toBeInTheDocument();
  });

  it("syntax highlights fenced diff blocks", () => {
    const { container } = render(
      <MarkdownMessage content={"```diff\n- expected\n+ received\n```"} />,
    );

    expect(container.querySelector("code.language-diff")).toBeInTheDocument();
    expect(container.querySelector(".token.deleted")).toHaveTextContent(
      "- expected",
    );
    expect(container.querySelector(".token.inserted")).toHaveTextContent(
      "+ received",
    );
  });
});

describe("ExpandableMarkdownMessage", () => {
  it("renders short content directly without toggle button", () => {
    render(
      <ExpandableMarkdownMessage
        content="Short content"
        previewCharacters={50}
      />,
    );
    expect(screen.getByText("Short content")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders truncated preview when collapsed and replaces it with full content when expanded", () => {
    const fullText =
      "First sentence of the assessment. Second sentence with sensitive details.";
    render(
      <ExpandableMarkdownMessage content={fullText} previewCharacters={33} />,
    );

    expect(
      screen.getByText("First sentence of the assessment.…"),
    ).toBeInTheDocument();
    const button = screen.getByRole("button", {
      name: "Show full justification",
    });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("aria-expanded", "false");

    // Click to expand
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(
      screen.getByRole("button", { name: "Hide full justification" }),
    ).toBeInTheDocument();

    // Full text should be visible and the truncated preview should no longer be rendered
    expect(screen.getByText(fullText)).toBeInTheDocument();
    expect(
      screen.queryByText("First sentence of the assessment.…"),
    ).not.toBeInTheDocument();

    // Click to collapse
    fireEvent.click(button);
    expect(
      screen.getByRole("button", { name: "Show full justification" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("First sentence of the assessment.…"),
    ).toBeInTheDocument();
    expect(screen.queryByText(fullText)).not.toBeInTheDocument();
  });
});
