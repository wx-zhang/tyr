import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DecodingProvenance } from "./DecodingProvenance";
import type { ContentOverlapResult } from "../../api/generated";

describe("DecodingProvenance", () => {
  it("renders nothing when decoding provenance is omitted or undefined (legacy)", () => {
    const { container } = render(<DecodingProvenance decoding={undefined} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders quiet status for skipped decoding without lineage dump", () => {
    render(
      <DecodingProvenance
        decoding={{
          status: "skipped",
          attemptCount: 0,
        }}
      />,
    );

    const section = screen.getByRole("region", {
      name: "Trajectory decoding provenance",
    });
    expect(section).toBeInTheDocument();
    expect(within(section).getByText("Trajectory decoding")).toBeInTheDocument();
    expect(within(section).getByText("Skipped")).toBeInTheDocument();
    expect(within(section).getByText("0")).toBeInTheDocument();
    expect(within(section).queryByRole("list")).not.toBeInTheDocument();
    expect(
      within(section).queryByText(/Derived files/i),
    ).not.toBeInTheDocument();
  });

  it("renders status, attempts, and safe failure code for failed decoding without exception text", () => {
    render(
      <DecodingProvenance
        decoding={{
          status: "failed",
          attemptCount: 3,
          failureCode: "attempt_exhaustion",
          limitFlags: {
            timedOut: true,
            outputLimited: false,
          },
        }}
      />,
    );

    const section = screen.getByRole("region", {
      name: "Trajectory decoding provenance",
    });
    expect(section).toBeInTheDocument();
    expect(within(section).getByText("Failed")).toBeInTheDocument();
    expect(within(section).getByText("3")).toBeInTheDocument();
    expect(within(section).getByText("Attempt Exhaustion")).toBeInTheDocument();
    expect(within(section).getByText("Timed out")).toBeInTheDocument();
    // Verify no stack trace or raw exception text is displayed
    expect(within(section).queryByText(/exception/i)).not.toBeInTheDocument();
    expect(within(section).queryByText(/traceback/i)).not.toBeInTheDocument();
  });

  it("renders status, attempts, and bounded lineage for successful decoding", () => {
    render(
      <DecodingProvenance
        decoding={{
          status: "succeeded",
          attemptCount: 1,
          derivedFiles: [
            {
              sourceFileId: "src-file-123",
              uploadedItemId: "item-456",
              sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
              size: 2048,
              detectedContentType: "text/plain",
            },
          ],
        }}
      />,
    );

    const section = screen.getByRole("region", {
      name: "Trajectory decoding provenance",
    });
    expect(section).toBeInTheDocument();
    expect(within(section).getByText("Succeeded")).toBeInTheDocument();
    expect(within(section).getByText("1")).toBeInTheDocument();
    expect(within(section).getByText("Derived files")).toBeInTheDocument();
    expect(within(section).getByText("item-456")).toBeInTheDocument();
    expect(within(section).getByText("src-file-123")).toBeInTheDocument();
    expect(within(section).getByText("text/plain")).toBeInTheDocument();
    expect(within(section).getByText("2.0 KB")).toBeInTheDocument();
    expect(within(section).getByText("e3b0c442...b855")).toBeInTheDocument();
  });

  it("never renders generated source code, decoded content bytes, or sandbox container IDs", () => {
    const sensitiveSourceCode = "def decode_secret(): return 'secret_key_123'";
    const sensitiveDecodedContent = "super_secret_decrypted_password";
    const sensitiveSandboxId = "sandbox-docker-container-xyz987";

    const decodingData = {
      status: "succeeded" as const,
      attemptCount: 1,
      programSha256: [
        "1111111111111111111111111111111111111111111111111111111111111111",
      ],
      derivedFiles: [
        {
          sourceFileId: "file-safe-id",
          uploadedItemId: "item-safe-id",
          sha256: "2222222222222222222222222222222222222222222222222222222222222222",
          size: 512,
          detectedContentType: "text/plain",
        },
      ],
    };

    const { container } = render(<DecodingProvenance decoding={decodingData} />);
    const textContent = container.textContent ?? "";

    expect(textContent).not.toContain(sensitiveSourceCode);
    expect(textContent).not.toContain(sensitiveDecodedContent);
    expect(textContent).not.toContain(sensitiveSandboxId);
    expect(textContent).not.toContain("/var/run/docker");
    expect(textContent).not.toContain("/tmp/gamr");
  });
});
