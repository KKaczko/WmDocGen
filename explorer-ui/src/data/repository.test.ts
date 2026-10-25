import { describe, expect, it } from "vitest";

import type { FetchLike } from "./repository";
import {
  ContractMismatchError,
  DataLoadError,
  NotFoundError,
  StaticJsonRepository,
} from "./repository";

function fakeFetch(files: Record<string, unknown>, calls: string[] = []): FetchLike {
  return (url) => {
    calls.push(url);
    if (!(url in files)) return Promise.resolve(new Response("missing", { status: 404 }));
    const body = files[url];
    return Promise.resolve(
      new Response(typeof body === "string" ? body : JSON.stringify(body), { status: 200 }),
    );
  };
}

const ID = "0123456789abcdef";

describe("StaticJsonRepository", () => {
  it("loads each file once and checks the contract version", async () => {
    const calls: string[] = [];
    const repository = new StaticJsonRepository(
      "data/",
      fakeFetch({ "data/manifest.json": { contract: "wm-doc-explorer.v1", counts: {} } }, calls),
    );
    await repository.manifest();
    await repository.manifest();
    expect(calls).toEqual(["data/manifest.json"]);
  });

  it("rejects data written for another contract version", async () => {
    const repository = new StaticJsonRepository(
      "data/",
      fakeFetch({ "data/search.json": { contract: "wm-doc-explorer.v2" } }),
    );
    await expect(repository.search()).rejects.toBeInstanceOf(ContractMismatchError);
  });

  it("only builds paths from well-formed IDs", async () => {
    const calls: string[] = [];
    const repository = new StaticJsonRepository("data/", fakeFetch({}, calls));
    for (const bad of ["../manifest", "ABCDEF0123456789", "0123", `${ID}/../x`, "orders.api:x"]) {
      await expect(repository.service(bad)).rejects.toBeInstanceOf(NotFoundError);
    }
    expect(calls).toEqual([]);
  });

  it("reports missing files and broken JSON distinctly, and retries after a failure", async () => {
    const files: Record<string, unknown> = { [`data/services/${ID}.json`]: "{not json" };
    const repository = new StaticJsonRepository("data/", fakeFetch(files));
    await expect(repository.service("fedcba9876543210")).rejects.toBeInstanceOf(NotFoundError);
    await expect(repository.service(ID)).rejects.toBeInstanceOf(DataLoadError);
    files[`data/services/${ID}.json`] = { contract: "wm-doc-explorer.v1", id: ID };
    await expect(repository.service(ID)).resolves.toMatchObject({ id: ID });
  });
});
