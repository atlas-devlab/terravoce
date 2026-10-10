#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { compileTerraLex } from "./compiler.js";

const [, , command, input] = process.argv;

if (command !== "compile" || input === undefined) {
  console.error("usage: terralex compile <policy.terra>");
  process.exitCode = 1;
} else {
  const source = await readFile(resolve(input), "utf8");
  const bundle = compileTerraLex(source);
  console.log(
    JSON.stringify(
      {
        policyHash: bundle.policyHash,
        policy: bundle.policy
      },
      null,
      2
    )
  );
}

