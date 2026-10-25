import { useEffect, useState } from "react";

export type Resource<T> =
  | { readonly status: "loading" }
  | { readonly status: "ready"; readonly data: T }
  | { readonly status: "error"; readonly error: Error };

/** Load something asynchronously; reloads when `key` changes and ignores stale answers. */
export function useResource<T>(load: () => Promise<T>, key: string): Resource<T> {
  const [state, setState] = useState<{ key: string; resource: Resource<T> }>({
    key,
    resource: { status: "loading" },
  });

  useEffect(() => {
    let current = true;
    load().then(
      (data) => {
        if (current) setState({ key, resource: { status: "ready", data } });
      },
      (error: unknown) => {
        if (current) {
          const failure = error instanceof Error ? error : new Error(String(error));
          setState({ key, resource: { status: "error", error: failure } });
        }
      },
    );
    return () => {
      current = false;
    };
    // `load` is recreated on every render; `key` names what it loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return state.key === key ? state.resource : { status: "loading" };
}
