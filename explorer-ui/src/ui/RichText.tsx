import { Link } from "react-router";

import type { PathStep, Segment } from "../contract";
import { servicePath } from "./labels";

/**
 * Renders text from the data. Every segment becomes a React text node or a <code> element;
 * nothing is parsed as HTML or Markdown. Only a code segment that Python marked with the ID of
 * an analysed service becomes a link.
 */
export function RichText({ segments }: { segments: readonly Segment[] }) {
  return (
    <>
      {segments.map((segment, index) => {
        const key = String(index);
        if (segment.kind === "text") return <span key={key}>{segment.text}</span>;
        if (segment.ref !== null) {
          return (
            <Link key={key} to={servicePath(segment.code)} className="code-link">
              <code>{segment.code}</code>
            </Link>
          );
        }
        return <code key={key}>{segment.code}</code>;
      })}
    </>
  );
}

/** A call chain such as entry service → … → this service; analysed services are links. */
export function PathChain({ steps }: { steps: readonly PathStep[] }) {
  return (
    <span className="path-chain">
      {steps.map((step, index) => (
        <span key={`${step.name}-${String(index)}`}>
          {index > 0 ? <span aria-hidden="true"> → </span> : null}
          {index > 0 ? <span className="visually-hidden"> then </span> : null}
          {step.id !== null ? (
            <Link to={servicePath(step.name)} className="code-link">
              <code>{step.name}</code>
            </Link>
          ) : (
            <code>{step.name}</code>
          )}
        </span>
      ))}
    </span>
  );
}
