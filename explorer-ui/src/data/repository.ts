import type {
  GraphData,
  Manifest,
  PackageDetail,
  SearchIndex,
  ServerOverview,
  ServiceDetail,
} from "../contract";
import { CONTRACT, ID_PATTERN } from "../contract";

/**
 * Where the app gets its data. Today the files written by `wm-doc explorer build`; a future
 * REST backend implements the same interface and nothing else in the app changes.
 */
export interface ExplorerRepository {
  manifest(): Promise<Manifest>;
  search(): Promise<SearchIndex>;
  service(id: string): Promise<ServiceDetail>;
  /** Every call, for the graph view; loaded on first use. */
  graph(): Promise<GraphData>;
  package(id: string): Promise<PackageDetail>;
  /** The server overview description and the packages left out of the analysis. */
  overview(): Promise<ServerOverview>;
}

export class NotFoundError extends Error {
  override name = "NotFoundError";
}

export class ContractMismatchError extends Error {
  override name = "ContractMismatchError";
  constructor(readonly found: string) {
    super(`The data uses contract ${found}; this app reads ${CONTRACT}.`);
  }
}

export class DataLoadError extends Error {
  override name = "DataLoadError";
}

export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

const defaultFetch: FetchLike = (url, init) => fetch(url, init);

/** Reads the static JSON files next to the app, once each. */
export class StaticJsonRepository implements ExplorerRepository {
  readonly #cache = new Map<string, Promise<unknown>>();
  readonly #baseUrl: string;
  readonly #fetch: FetchLike;

  constructor(baseUrl = "data/", fetchImpl: FetchLike = defaultFetch) {
    this.#baseUrl = baseUrl;
    this.#fetch = fetchImpl;
  }

  manifest(): Promise<Manifest> {
    return this.#get<Manifest>("manifest.json");
  }

  search(): Promise<SearchIndex> {
    return this.#get<SearchIndex>("search.json");
  }

  graph(): Promise<GraphData> {
    return this.#get<GraphData>("graph.json");
  }

  overview(): Promise<ServerOverview> {
    return this.#get<ServerOverview>("overview.json");
  }

  package(id: string): Promise<PackageDetail> {
    if (!ID_PATTERN.test(id)) {
      return Promise.reject(new NotFoundError("Not a package ID."));
    }
    return this.#get<PackageDetail>(`packages/${id}.json`);
  }

  service(id: string): Promise<ServiceDetail> {
    if (!ID_PATTERN.test(id)) {
      return Promise.reject(new NotFoundError("Not a service ID."));
    }
    return this.#get<ServiceDetail>(`services/${id}.json`);
  }

  #get<T>(path: string): Promise<T> {
    let pending = this.#cache.get(path);
    if (pending === undefined) {
      pending = this.#load(path);
      this.#cache.set(path, pending);
      // A failed load may succeed later (for example after a rebuild), so it is not kept.
      pending.catch(() => this.#cache.delete(path));
    }
    return pending as Promise<T>;
  }

  async #load(path: string): Promise<unknown> {
    let response: Response;
    try {
      response = await this.#fetch(`${this.#baseUrl}${path}`, {
        credentials: "same-origin",
        cache: "no-cache",
      });
    } catch {
      throw new DataLoadError(`Could not load ${path}.`);
    }
    if (response.status === 404) {
      throw new NotFoundError(`${path} is not in this export.`);
    }
    if (!response.ok) {
      throw new DataLoadError(`Loading ${path} failed (HTTP ${String(response.status)}).`);
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      throw new DataLoadError(`${path} is not valid JSON.`);
    }
    const contract =
      typeof payload === "object" && payload !== null && "contract" in payload
        ? String(payload.contract)
        : "none";
    if (contract !== CONTRACT) {
      throw new ContractMismatchError(contract);
    }
    return payload;
  }
}
