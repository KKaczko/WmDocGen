import { createContext, useContext } from "react";

import type { Manifest, SearchIndex, SearchPackage, SearchService } from "../contract";
import type { Searcher } from "../domain/search";
import type { ExplorerRepository } from "./repository";

/** What every page needs: the repository and the index loaded once at start. */
export interface Explorer {
  readonly repository: ExplorerRepository;
  readonly manifest: Manifest;
  readonly search: SearchIndex;
  readonly searcher: Searcher;
  /** Exact service name -> its entries (more than one only for duplicate names). */
  readonly servicesByName: ReadonlyMap<string, readonly SearchService[]>;
  /** Exact package name -> its search entry. */
  readonly packagesByName: ReadonlyMap<string, SearchPackage>;
}

export const ExplorerContext = createContext<Explorer | null>(null);

export function useExplorer(): Explorer {
  const explorer = useContext(ExplorerContext);
  if (explorer === null) {
    throw new Error("useExplorer must be used inside the loaded explorer.");
  }
  return explorer;
}

export function indexServicesByName(
  services: readonly SearchService[],
): ReadonlyMap<string, readonly SearchService[]> {
  const byName = new Map<string, SearchService[]>();
  for (const service of services) {
    const list = byName.get(service.name);
    if (list === undefined) byName.set(service.name, [service]);
    else list.push(service);
  }
  return byName;
}
