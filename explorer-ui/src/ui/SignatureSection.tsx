import type { Signature, SignatureField } from "../contract";
import { SectionHeading } from "./SectionHeading";

export function SignatureSection({ signature }: { signature: Signature }) {
  return (
    <section className="section" aria-labelledby="signature-title">
      <SectionHeading id="signature-title" source="analysis">
        Signature
      </SectionHeading>
      {signature.origin === "specification" && signature.specification !== null ? (
        <p className="note">
          Taken from the specification <code>{signature.specification}</code>.
        </p>
      ) : null}
      <div className="signature">
        <FieldList title="Input" fields={signature.inputs} />
        <FieldList title="Output" fields={signature.outputs} />
      </div>
      {signature.truncated ? (
        <p className="note">The signature is large; only its first fields are shown.</p>
      ) : null}
    </section>
  );
}

// Designer type names, in words.
const TYPE_LABEL: Readonly<Record<string, string>> = {
  recref: "document reference",
  record: "document",
  string: "string",
  object: "object",
};

function FieldList({ title, fields }: { title: string; fields: readonly SignatureField[] }) {
  return (
    <div>
      <h3>{title}</h3>
      {fields.length === 0 ? <p className="muted">No fields.</p> : <Fields fields={fields} />}
    </div>
  );
}

function Fields({ fields }: { fields: readonly SignatureField[] }) {
  return (
    <ul className="fields">
      {fields.map((field, index) => (
        <li key={`${field.name}-${String(index)}`}>
          <code className="field-name">{field.name}</code>
          <span className="field-type">
            {field.type === null ? "unknown" : (TYPE_LABEL[field.type] ?? field.type)}
            {field.dimension > 0 ? "[]".repeat(field.dimension) : ""}
          </span>
          {field.optional === true ? <span className="muted"> optional</span> : null}
          {field.document !== null ? (
            <span className={field.document.resolved ? "doc-ref" : "doc-ref missing"}>
              {" "}
              <code>{field.document.name}</code>
              {field.document.resolved ? null : " (document type not found)"}
            </span>
          ) : null}
          {field.children.length > 0 ? <Fields fields={field.children} /> : null}
        </li>
      ))}
    </ul>
  );
}
