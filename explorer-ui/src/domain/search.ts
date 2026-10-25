import type { SearchIndex, SearchPackage, SearchService } from "../contract";

/**
 * Ranked search over service and package names, namespaces and purpose lines.
 *
 * Every query word must match. A word scores by how it matches, best first: the whole
 * name, the service's short name, a name prefix, the start of a namespace segment or of a
 * camelCase word, anywhere in the name, the package name, the start of a word in the purpose
 * line. Ties go to the shorter name, then alphabetical order, so results are deterministic.
 */

export type SearchHit =
  | { readonly type: "service"; readonly score: number; readonly item: SearchService }
  | { readonly type: "package"; readonly score: number; readonly item: SearchPackage };

interface Entry {
  readonly hit: Omit<SearchHit, "score">;
  readonly id: string;
  /** Lower-case full name: matched against, and the tie-break order. */
  readonly name: string;
  readonly shortName: string;
  readonly words: readonly string[];
  readonly packageName: string;
  readonly purposeWords: readonly string[];
}

export interface Searcher {
  query(text: string, limits?: { services?: number; packages?: number }): SearchHit[];
}

const SEPARATORS = /[.:_\s/-]+/;
const CAMEL_BOUNDARY = /(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])/;

/** Lower-case words of a name: namespace segments and their camelCase parts. */
export function nameWords(name: string): string[] {
  const words = new Set<string>();
  for (const segment of name.split(SEPARATORS)) {
    if (segment === "") continue;
    words.add(segment.toLowerCase());
    for (const part of segment.split(CAMEL_BOUNDARY)) {
      if (part !== "") words.add(part.toLowerCase());
    }
  }
  return [...words];
}

function purposeWords(purpose: string | null): string[] {
  if (purpose === null) return [];
  return [
    ...new Set(
      purpose
        .toLowerCase()
        .split(/[^\p{L}\p{N}]+/u)
        .filter(Boolean),
    ),
  ];
}

function scoreWord(entry: Entry, word: string): number {
  if (entry.name === word) return 1000;
  if (entry.shortName === word) return 900;
  if (entry.name.startsWith(word)) return 800;
  if (entry.shortName.startsWith(word)) return 700;
  if (entry.words.some((part) => part.startsWith(word))) return 600;
  if (entry.name.includes(word)) return 500;
  if (entry.packageName.includes(word)) return 300;
  if (entry.purposeWords.some((part) => part.startsWith(word))) return 200;
  return 0;
}

interface Match {
  readonly entry: Entry;
  readonly score: number;
}

// A one-letter query can match every service, so this runs thousands of times per keystroke:
// it compares precomputed lower-case names by code unit (no locale rules, same in every
// browser) instead of calling localeCompare.
function compareMatches(a: Match, b: Match): number {
  if (a.score !== b.score) return b.score - a.score;
  const left = a.entry.name;
  const right = b.entry.name;
  if (left.length !== right.length) return left.length - right.length;
  if (left !== right) return left < right ? -1 : 1;
  return a.entry.id < b.entry.id ? -1 : a.entry.id > b.entry.id ? 1 : 0;
}

function top(matches: Match[], limit: number): SearchHit[] {
  matches.sort(compareMatches);
  return matches
    .slice(0, limit)
    .map((match) => ({ ...match.entry.hit, score: match.score }) as SearchHit);
}

export function createSearcher(index: SearchIndex): Searcher {
  const entries: Entry[] = [
    ...index.services.map((item) => {
      const shortName = item.name.slice(item.name.lastIndexOf(":") + 1);
      return {
        hit: { type: "service" as const, item },
        id: item.id,
        name: item.name.toLowerCase(),
        shortName: shortName.toLowerCase(),
        words: nameWords(item.name),
        packageName: item.package.toLowerCase(),
        purposeWords: purposeWords(item.purpose),
      };
    }),
    ...index.packages.map((item) => ({
      hit: { type: "package" as const, item },
      id: item.id,
      name: item.name.toLowerCase(),
      shortName: item.name.toLowerCase(),
      words: nameWords(item.name),
      packageName: "",
      purposeWords: purposeWords(item.purpose),
    })),
  ];

  return {
    query(text, limits = {}) {
      const words = text.toLowerCase().split(/\s+/).filter(Boolean);
      if (words.length === 0) return [];
      const services: Match[] = [];
      const packages: Match[] = [];
      for (const entry of entries) {
        let total = 0;
        for (const word of words) {
          const score = scoreWord(entry, word);
          if (score === 0) {
            total = 0;
            break;
          }
          total += score;
        }
        if (total === 0) continue;
        (entry.hit.type === "service" ? services : packages).push({ entry, score: total });
      }
      return [...top(services, limits.services ?? 20), ...top(packages, limits.packages ?? 6)];
    },
  };
}
