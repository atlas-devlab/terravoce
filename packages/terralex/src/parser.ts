import {
  createToken,
  EmbeddedActionsParser,
  Lexer,
  type IToken,
  tokenMatcher
} from "chevrotain";

import type {
  DurationUnit,
  TerraLexAst,
  TerraLexStatement
} from "./types.js";

const WhiteSpace = createToken({
  name: "WhiteSpace",
  pattern: /\s+/,
  group: Lexer.SKIPPED
});
const LineComment = createToken({
  name: "LineComment",
  pattern: /#[^\r\n]*/,
  group: Lexer.SKIPPED
});
const Policy = createToken({ name: "Policy", pattern: /policy\b/ });
const Version = createToken({ name: "Version", pattern: /version\b/ });
const Region = createToken({ name: "Region", pattern: /region\b/ });
const Metric = createToken({ name: "Metric", pattern: /metric\b/ });
const When = createToken({ name: "When", pattern: /when\b/ });
const Risk = createToken({ name: "Risk", pattern: /risk\b/ });
const Confidence = createToken({ name: "Confidence", pattern: /confidence\b/ });
const Observations = createToken({ name: "Observations", pattern: /observations\b/ });
const And = createToken({ name: "And", pattern: /and\b/ });
const Allow = createToken({ name: "Allow", pattern: /allow\b/ });
const Reversible = createToken({ name: "Reversible", pattern: /reversible\b/ });
const Budget = createToken({ name: "Budget", pattern: /budget\b/ });
const Per = createToken({ name: "Per", pattern: /per\b/ });
const Challenge = createToken({ name: "Challenge", pattern: /challenge\b/ });
const Require = createToken({ name: "Require", pattern: /require\b/ });
const Community = createToken({ name: "Community", pattern: /community\b/ });
const Guardian = createToken({ name: "Guardian", pattern: /guardian\b/ });
const Pause = createToken({ name: "Pause", pattern: /pause\b/ });
const Forbid = createToken({ name: "Forbid", pattern: /forbid\b/ });
const Irreversible = createToken({ name: "Irreversible", pattern: /irreversible\b/ });
const Hours = createToken({ name: "Hours", pattern: /hours\b/ });
const Days = createToken({ name: "Days", pattern: /days\b/ });
const GreaterEqual = createToken({ name: "GreaterEqual", pattern: />=/ });
const LeftBrace = createToken({ name: "LeftBrace", pattern: /\{/ });
const RightBrace = createToken({ name: "RightBrace", pattern: /\}/ });
const Semicolon = createToken({ name: "Semicolon", pattern: /;/ });
const StringLiteral = createToken({
  name: "StringLiteral",
  pattern: /"(?:[^"\\]|\\["\\nrt])*"/
});
const NumberLiteral = createToken({
  name: "NumberLiteral",
  pattern: /(?:0|[1-9]\d*)(?:\.\d+)?/
});
const Identifier = createToken({
  name: "Identifier",
  pattern: /[A-Za-z][A-Za-z0-9_-]*/
});

const allTokens = [
  WhiteSpace,
  LineComment,
  Policy,
  Version,
  Region,
  Metric,
  When,
  Risk,
  Confidence,
  Observations,
  And,
  Allow,
  Reversible,
  Budget,
  Per,
  Challenge,
  Require,
  Community,
  Guardian,
  Pause,
  Forbid,
  Irreversible,
  Hours,
  Days,
  GreaterEqual,
  LeftBrace,
  RightBrace,
  Semicolon,
  StringLiteral,
  NumberLiteral,
  Identifier
];

const lexer = new Lexer(allTokens);

const decodeString = (token: IToken): string =>
  JSON.parse(token.image) as string;

const numberValue = (token: IToken): number => Number(token.image);

class TerraLexParser extends EmbeddedActionsParser {
  public policy = this.RULE("policy", (): TerraLexAst => {
    this.CONSUME(Policy);
    const name = this.CONSUME(StringLiteral);
    this.CONSUME(Version);
    const version = this.CONSUME(NumberLiteral);
    this.CONSUME(LeftBrace);
    const statements: TerraLexStatement[] = [];
    this.AT_LEAST_ONE(() => {
      const statement = this.SUBRULE(this.statement);
      this.ACTION(() => statements.push(statement));
    });
    this.CONSUME(RightBrace);
    return this.ACTION(() => ({
      name: decodeString(name),
      version: numberValue(version),
      statements
    }));
  });

  private statement = this.RULE("statement", (): TerraLexStatement =>
    this.OR([
      { ALT: () => this.SUBRULE(this.regionStatement) },
      { ALT: () => this.SUBRULE(this.metricStatement) },
      { ALT: () => this.SUBRULE(this.whenStatement) },
      { ALT: () => this.SUBRULE(this.allowStatement) },
      { ALT: () => this.SUBRULE(this.budgetStatement) },
      { ALT: () => this.SUBRULE(this.challengeStatement) },
      { ALT: () => this.SUBRULE(this.requireStatement) },
      { ALT: () => this.SUBRULE(this.forbidStatement) }
    ])
  );

  private regionStatement = this.RULE("regionStatement", (): TerraLexStatement => {
    this.CONSUME(Region);
    const value = this.CONSUME(StringLiteral);
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({ kind: "region", value: decodeString(value) }));
  });

  private metricStatement = this.RULE("metricStatement", (): TerraLexStatement => {
    this.CONSUME(Metric);
    const value = this.CONSUME(StringLiteral);
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({ kind: "metric", value: decodeString(value) }));
  });

  private condition = this.RULE(
    "condition",
    (): Extract<TerraLexStatement, { kind: "when" }>["conditions"][number] => {
      const field = this.OR([
        { ALT: () => this.CONSUME(Risk) },
        { ALT: () => this.CONSUME(Confidence) },
        { ALT: () => this.CONSUME(Observations) }
      ]);
      this.CONSUME(GreaterEqual);
      const value = this.CONSUME(NumberLiteral);
      return this.ACTION(() => ({
        field: field.image as "risk" | "confidence" | "observations",
        value: numberValue(value)
      }));
    }
  );

  private whenStatement = this.RULE("whenStatement", (): TerraLexStatement => {
    this.CONSUME(When);
    const conditions = [this.SUBRULE(this.condition)];
    this.MANY(() => {
      this.CONSUME(And);
      const condition = this.SUBRULE2(this.condition);
      this.ACTION(() => conditions.push(condition));
    });
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({ kind: "when", conditions }));
  });

  private allowStatement = this.RULE("allowStatement", (): TerraLexStatement => {
    this.CONSUME(Allow);
    const action = this.CONSUME(StringLiteral);
    this.CONSUME(Reversible);
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({
      kind: "allow",
      action: decodeString(action),
      reversible: true
    }));
  });

  private durationUnit = this.RULE("durationUnit", (): DurationUnit => {
    const unit = this.OR([
      { ALT: () => this.CONSUME(Hours) },
      { ALT: () => this.CONSUME(Days) }
    ]);
    return this.ACTION(() => (tokenMatcher(unit, Hours) ? "hours" : "days"));
  });

  private budgetStatement = this.RULE("budgetStatement", (): TerraLexStatement => {
    this.CONSUME(Budget);
    const amount = this.CONSUME(NumberLiteral);
    const asset = this.CONSUME(Identifier);
    this.CONSUME(Per);
    const period = this.CONSUME2(NumberLiteral);
    const unit = this.SUBRULE(this.durationUnit);
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({
      kind: "budget",
      amount: numberValue(amount),
      asset: asset.image,
      period: numberValue(period),
      unit
    }));
  });

  private challengeStatement = this.RULE(
    "challengeStatement",
    (): TerraLexStatement => {
      this.CONSUME(Challenge);
      const duration = this.CONSUME(NumberLiteral);
      const unit = this.SUBRULE(this.durationUnit);
      this.CONSUME(Semicolon);
      return this.ACTION(() => ({
        kind: "challenge",
        duration: numberValue(duration),
        unit
      }));
    }
  );

  private requireStatement = this.RULE("requireStatement", (): TerraLexStatement => {
    this.CONSUME(Require);
    return this.OR([
      {
        ALT: () => {
          this.CONSUME(Community);
          this.CONSUME(Challenge);
          this.CONSUME(Semicolon);
          return this.ACTION(
            () => ({ kind: "require-community-challenge" }) as const
          );
        }
      },
      {
        ALT: () => {
          this.CONSUME(Guardian);
          this.CONSUME(Pause);
          this.CONSUME2(Semicolon);
          return this.ACTION(() => ({ kind: "require-guardian-pause" }) as const);
        }
      }
    ]);
  });

  private forbidStatement = this.RULE("forbidStatement", (): TerraLexStatement => {
    this.CONSUME(Forbid);
    this.CONSUME(Irreversible);
    this.CONSUME(Semicolon);
    return this.ACTION(() => ({ kind: "forbid-irreversible" }));
  });

  public constructor() {
    super(allTokens);
    this.performSelfAnalysis();
  }
}

const parser = new TerraLexParser();

export class TerraLexSyntaxError extends Error {
  public constructor(public readonly diagnostics: string[]) {
    super(diagnostics.join("\n"));
    this.name = "TerraLexSyntaxError";
  }
}

export const parseTerraLex = (source: string): TerraLexAst => {
  const lexed = lexer.tokenize(source);
  if (lexed.errors.length > 0) {
    throw new TerraLexSyntaxError(
      lexed.errors.map((error) => `line ${error.line ?? "?"}: ${error.message}`)
    );
  }

  parser.input = lexed.tokens;
  const ast = parser.policy();
  if (parser.errors.length > 0) {
    throw new TerraLexSyntaxError(
      parser.errors.map((error) => {
        const line = error.token.startLine ?? "?";
        return `line ${line}: ${error.message}`;
      })
    );
  }
  return ast;
};
