import { expect, it } from "vitest";
import { parseDiscoveryInputDocument } from "./discoveryInput";

const validDocument = {
  schemaVersion: "1.0",
  kind: "discovery-input",
  taskId: "informational-task-id",
  candidate: {
    path: "/home/alice/work",
    workspace: "peer",
    agent: "Alice",
    bridgeId: "bridge-1",
  },
};

it("parses a strict discovery input document", () => {
  const result = parseDiscoveryInputDocument(JSON.stringify(validDocument));

  expect(result).toEqual({ ok: true, document: validDocument });
});

it.each([
  ["extra document field", { ...validDocument, extra: true }],
  ["extra candidate field", { ...validDocument, candidate: { ...validDocument.candidate, extra: true } }],
  ["empty path", { ...validDocument, candidate: { ...validDocument.candidate, path: "" } }],
  ["empty agent", { ...validDocument, candidate: { ...validDocument.candidate, agent: "" } }],
  ["missing workspace", { ...validDocument, candidate: { bridgeId: "bridge-1" } }],
  ["missing bridge", { ...validDocument, candidate: { workspace: "Dorian" } }],
])("rejects %s", (_label, document) => {
  const result = parseDiscoveryInputDocument(JSON.stringify(document));

  expect(result.ok).toBe(false);
});

it.each(["/srv/data", "relative/path", "Dorian -> Mira"])("accepts Task-defined path %s", (path) => {
  const document = { ...validDocument, candidate: { ...validDocument.candidate, path } };

  expect(parseDiscoveryInputDocument(JSON.stringify(document))).toEqual({ ok: true, document });
});

it("accepts a workspace and Bridge without a path or Agent", () => {
  const document = { ...validDocument, candidate: { workspace: "Dorian", bridgeId: "bridge-1" } };

  expect(parseDiscoveryInputDocument(JSON.stringify(document))).toEqual({ ok: true, document });
});
