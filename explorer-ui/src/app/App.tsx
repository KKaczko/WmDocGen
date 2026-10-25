import { useMemo } from "react";
import { RouterProvider, createHashRouter } from "react-router";

import type { Explorer } from "../data/explorer-context";
import { ExplorerContext, indexServicesByName } from "../data/explorer-context";
import type { ExplorerRepository } from "../data/repository";
import { ContractMismatchError } from "../data/repository";
import { useResource } from "../data/use-resource";
import { createSearcher } from "../domain/search";
import { HomePage } from "../ui/HomePage";
import { Layout } from "../ui/Layout";
import { NotFoundPage } from "../ui/NotFoundPage";
import { PackagePage } from "../ui/PackagePage";
import { ServicePage } from "../ui/ServicePage";

// Hash routes work on any static server: no server-side fallback is needed.
const router = createHashRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "s/:name", element: <ServicePage /> },
      { path: "p/:name", element: <PackagePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

async function loadExplorer(repository: ExplorerRepository): Promise<Explorer> {
  const [manifest, search] = await Promise.all([repository.manifest(), repository.search()]);
  return {
    repository,
    manifest,
    search,
    searcher: createSearcher(search),
    servicesByName: indexServicesByName(search.services),
    packagesByName: new Map(search.packages.map((item) => [item.name, item])),
  };
}

export function App({ repository }: { repository: ExplorerRepository }) {
  const load = useMemo(() => () => loadExplorer(repository), [repository]);
  const explorer = useResource(load, "explorer");

  if (explorer.status === "loading") {
    return (
      <p className="status-line" role="status">
        Loading the explorer…
      </p>
    );
  }
  if (explorer.status === "error") {
    const error = explorer.error;
    return (
      <section className="message-page" role="alert">
        <h1>The explorer data could not be loaded</h1>
        <p>{error.message}</p>
        <p>
          {error instanceof ContractMismatchError
            ? "Rebuild the explorer with the wm-doc version that ships this app."
            : "Serve the folder with `wm-doc explorer serve <folder>`: browsers do not load it from file://."}
        </p>
      </section>
    );
  }
  return (
    <ExplorerContext.Provider value={explorer.data}>
      <RouterProvider router={router} />
    </ExplorerContext.Provider>
  );
}
