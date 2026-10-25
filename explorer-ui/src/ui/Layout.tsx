import { Link, Outlet } from "react-router";

import { useExplorer } from "../data/explorer-context";
import { SearchBox } from "./SearchBox";

export function Layout() {
  const { manifest } = useExplorer();
  const synthetic = manifest.dataset.kind === "synthetic";
  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <header className="topbar">
        <Link to="/" className="brand">
          WmDocGen Explorer
        </Link>
        <span
          className={synthetic ? "dataset dataset-synthetic" : "dataset dataset-private"}
          title={
            synthetic
              ? "Generated demo data: safe to show and share."
              : "Built from real packages: keep it internal."
          }
        >
          {synthetic ? manifest.dataset.label : `${manifest.dataset.label} — do not share`}
        </span>
        <SearchBox />
      </header>
      <main id="main" className="content">
        <Outlet />
      </main>
    </>
  );
}
