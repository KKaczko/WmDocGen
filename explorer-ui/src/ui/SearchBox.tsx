import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { useNavigate } from "react-router";

import { useExplorer } from "../data/explorer-context";
import type { SearchHit } from "../domain/search";
import { KIND_LABEL, packagePath, servicePath } from "./labels";

/** Global search: an ARIA combobox over services and packages. `/` focuses it. */
export function SearchBox() {
  const { searcher, servicesByName } = useExplorer();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const hits = useMemo(() => searcher.query(text), [searcher, text]);

  useEffect(() => {
    function focusOnSlash(event: globalThis.KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const typing =
        target !== null &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (event.key === "/" && !typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", focusOnSlash);
    return () => window.removeEventListener("keydown", focusOnSlash);
  }, []);

  function choose(hit: SearchHit) {
    setOpen(false);
    setText("");
    if (hit.type === "service") {
      const duplicates = (servicesByName.get(hit.item.name) ?? []).length > 1;
      void navigate(servicePath(hit.item.name, duplicates ? hit.item.package : undefined));
    } else {
      void navigate(packagePath(hit.item.name));
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setOpen(true);
      setActive((index) => Math.min(index + 1, Math.max(hits.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      const hit = hits[active];
      if (hit !== undefined) {
        event.preventDefault();
        choose(hit);
      }
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const expanded = open && text.trim() !== "";
  const optionId = (index: number) => `${listId}-option-${String(index)}`;

  return (
    <div className="search">
      <label htmlFor={`${listId}-input`} className="visually-hidden">
        Search services and packages
      </label>
      <input
        ref={inputRef}
        id={`${listId}-input`}
        className="search-input"
        type="search"
        role="combobox"
        aria-expanded={expanded}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={expanded && hits.length > 0 ? optionId(active) : undefined}
        placeholder="Search services and packages  ( / )"
        autoComplete="off"
        spellCheck={false}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setActive(0);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />
      <div
        id={listId}
        role="listbox"
        aria-label="Search results"
        className="search-results"
        hidden={!expanded}
      >
        {expanded && hits.length === 0 ? (
          <div className="search-empty">No service or package matches.</div>
        ) : null}
        {hits.map((hit, index) => (
          <div
            key={`${hit.type}-${hit.item.id}`}
            id={optionId(index)}
            role="option"
            tabIndex={-1}
            aria-selected={index === active}
            className={index === active ? "search-option active" : "search-option"}
            onMouseDown={(event) => {
              event.preventDefault();
              choose(hit);
            }}
            onMouseEnter={() => setActive(index)}
          >
            {hit.type === "service" ? (
              <>
                <span className="search-name">{hit.item.name}</span>
                <span className="search-meta">
                  {KIND_LABEL[hit.item.kind]} · {hit.item.package}
                </span>
                {hit.item.purpose !== null ? (
                  <span className="search-purpose">{hit.item.purpose}</span>
                ) : null}
              </>
            ) : (
              <>
                <span className="search-name">{hit.item.name}</span>
                <span className="search-meta">Package · {hit.item.services} services</span>
              </>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
