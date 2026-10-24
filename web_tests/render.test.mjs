import assert from "node:assert/strict";
import { test } from "node:test";

import { parseBlocks, parseInline } from "../src/hcm_ai/web/js/render.js";

test("bold segments are split out", () => {
  assert.deepEqual(parseInline("Hello **world** again"), [
    { text: "Hello ", bold: false },
    { text: "world", bold: true },
    { text: " again", bold: false },
  ]);
  assert.deepEqual(parseInline("plain"), [{ text: "plain", bold: false }]);
});

test("consecutive bullets form one list; other lines are paragraphs", () => {
  const blocks = parseBlocks("Intro\n- one\n- **two**\n• three\n\nOutro");
  assert.equal(blocks.length, 3);
  assert.equal(blocks[0].type, "p");
  assert.equal(blocks[1].type, "list");
  assert.equal(blocks[1].items.length, 3);
  assert.deepEqual(blocks[1].items[1], [{ text: "two", bold: true }]);
  assert.equal(blocks[2].type, "p");
});

test("blank input gives no blocks", () => {
  assert.deepEqual(parseBlocks(""), []);
  assert.deepEqual(parseBlocks(null), []);
});

test("HTML in model output stays literal text (never parsed as markup)", () => {
  const evil = '<img src=x onerror="alert(1)"> <script>steal()</script>';
  const [block] = parseBlocks(evil);
  assert.equal(block.type, "p");
  assert.equal(block.inline.map((p) => p.text).join(""), evil);
});
