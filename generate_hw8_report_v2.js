const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, BorderStyle, WidthType, ShadingType, VerticalAlign,
  LevelFormat
} = require('docx');
const fs = require('fs');
const path = require('path');

// Colors
const DARK_GREEN = "1a5c38";
const WHITE = "FFFFFF";
const LIGHT_GREEN = "e8f5ee";
const CALLOUT_GREEN = "d4edda";   // light green for callout box background
const CALLOUT_BORDER = "1a5c38"; // dark green border for callout
const GRAY_TEXT = "666666";
const LIGHT_GRAY = "f5f5f5";

// Page / layout constants (DXA units)
const PAGE_W = 12240;
const PAGE_H = 15840;
const MARGIN_TOP = 720;
const MARGIN_BOTTOM = 720;
const MARGIN_LEFT = 1080;
const MARGIN_RIGHT = 1080;
const CONTENT_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT; // 10080

// Font
const FONT = "Calibri";
const BASE_PT = 8.5;     // slightly reduced body to fit on one page
const TABLE_PT = 8.5;    // table cells
const HEADER_PT = 9.5;   // section headers
const TITLE_PT = 13;
const SUBTITLE_PT = 9.5;
const INFO_PT = 8.5;

// Helpers
function halfPt(pt) { return Math.round(pt * 2); }

function cellBorder(color = "CCCCCC") {
  const b = { style: BorderStyle.SINGLE, size: 1, color };
  return { top: b, bottom: b, left: b, right: b };
}

function noBorder() {
  const b = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return { top: b, bottom: b, left: b, right: b };
}

function sectionHeader(text) {
  return new Paragraph({
    spacing: { before: 70, after: 35 },
    children: [
      new TextRun({
        text,
        bold: true,
        size: halfPt(HEADER_PT),
        color: DARK_GREEN,
        font: FONT,
      })
    ]
  });
}

function bodyPara(text, opts = {}) {
  return new Paragraph({
    spacing: { before: 0, after: 35 },
    children: [
      new TextRun({
        text,
        size: halfPt(BASE_PT),
        font: FONT,
        italics: opts.italics || false,
        color: opts.color || "000000",
      })
    ]
  });
}

// Cell padding (compact)
const CELL_MARGINS = { top: 55, bottom: 55, left: 90, right: 90 };

function headerCell(text, width, center = false) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: cellBorder("1a5c38"),
    shading: { fill: DARK_GREEN, type: ShadingType.CLEAR },
    margins: CELL_MARGINS,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text, bold: true, color: WHITE, size: halfPt(TABLE_PT), font: FONT })]
    })]
  });
}

function dataCell(text, width, shade = false, center = false, bold = false) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders: cellBorder("CCCCCC"),
    shading: { fill: shade ? LIGHT_GREEN : "FFFFFF", type: ShadingType.CLEAR },
    margins: CELL_MARGINS,
    verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({
      alignment: center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text, size: halfPt(TABLE_PT), font: FONT, bold, color: "111111" })]
    })]
  });
}

// Callout box: single-cell table with light green background and dark green border
function calloutBox(lines) {
  const border = { style: BorderStyle.SINGLE, size: 8, color: CALLOUT_BORDER };
  const borders = { top: border, bottom: border, left: border, right: border };
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: [CONTENT_W],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: CONTENT_W, type: WidthType.DXA },
            borders,
            shading: { fill: CALLOUT_GREEN, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 140, right: 140 },
            children: lines.map(line => new Paragraph({
              spacing: { before: 0, after: 20 },
              children: [new TextRun({ text: line, bold: true, size: halfPt(TABLE_PT), font: FONT, color: "1a3d25" })]
            }))
          })
        ]
      })
    ]
  });
}

// ---- BUILD DOCUMENT ----

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "\u2022",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: 480, hanging: 240 },
              spacing: { before: 0, after: 18 },
            },
            run: { font: FONT, size: halfPt(BASE_PT) }
          }
        }]
      },
      {
        reference: "numbers",
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: "%1.",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: 480, hanging: 240 },
              spacing: { before: 0, after: 18 },
            },
            run: { font: FONT, size: halfPt(BASE_PT) }
          }
        }]
      }
    ]
  },

  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN_TOP, bottom: MARGIN_BOTTOM, left: MARGIN_LEFT, right: MARGIN_RIGHT }
      }
    },
    children: [

      // ---- TITLE BLOCK ----
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 18 },
        children: [new TextRun({ text: "HW8 Scale Experiment Report", bold: true, size: halfPt(TITLE_PT), color: DARK_GREEN, font: FONT })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 18 },
        children: [new TextRun({ text: "Agentic Reputation Infrastructure at 57 Agents", bold: true, size: halfPt(SUBTITLE_PT), color: DARK_GREEN, font: FONT })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 0, after: 55 },
        children: [new TextRun({ text: "MAS.664 AI Studio \u00B7 Team 8 \u00B7 MIT SFMBA 2026 \u00B7 aitrustlayer.vercel.app", size: halfPt(INFO_PT), color: GRAY_TEXT, font: FONT })]
      }),
      // Thin green horizontal rule
      new Paragraph({
        spacing: { before: 0, after: 70 },
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 6, color: DARK_GREEN, space: 1 }
        },
        children: []
      }),

      // ---- SECTION 1: What Changed Since HW7 ----
      sectionHeader("What Changed Since HW7"),
      bodyPara("HW7 validated the trust formula with 3 SkinScan agents running 2 rounds on 2 medical test cases \u2014 a narrow, manual proof-of-concept. HW8 scales the same infrastructure to 57 agents across 7 categories, runs fully automated multi-phase stress tests, and deliberately probes what breaks under load."),

      // Table 1: HW7 vs HW8 comparison
      (() => {
        const c0 = 2200, c1 = 3940, c2 = 3940;
        const rows_data = [
          ["Agents", "3", "57"],
          ["Categories", "1 (Medical)", "7"],
          ["Task rounds", "2 manual", "90 automated (30 agents \u00D7 3 rounds)"],
          ["Trust seeding", "Manual", "Automated bootstrap"],
          ["Cloud instances", "3 Railway services", "3 Railway + 54 via Vercel API"],
        ];
        return new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [c0, c1, c2],
          spacing: { before: 55, after: 55 },
          rows: [
            new TableRow({
              tableHeader: true,
              children: [
                headerCell("Dimension", c0),
                headerCell("HW7", c1, true),
                headerCell("HW8", c2, true),
              ]
            }),
            ...rows_data.map((r, i) => new TableRow({
              children: [
                dataCell(r[0], c0, i % 2 === 1, false, true),
                dataCell(r[1], c1, i % 2 === 1, true),
                dataCell(r[2], c2, i % 2 === 1, false),
              ]
            }))
          ]
        });
      })(),

      // ---- NEW SECTION: Trust Score Interpretability ----
      sectionHeader("Trust Score Interpretability"),
      bodyPara("Each agent\u2019s trust score reflects their track record \u2014 not just activity volume. More uses only helps if the work quality is good. Poor work at scale actively hurts trust."),

      // 3-column interpretability table
      (() => {
        const c0 = 3360, c1 = 2800, c2 = 3920;
        const rows_data = [
          ["Many tasks, all rated highly", "\u2705 Trust grows", "Volume + quality compound"],
          ["Many tasks, rated poorly", "\u274C Trust drops", "Uses rise but scores drag it down"],
          ["Feedback submitted, task incomplete", "\u274C TSR falls", "Completed/received ratio drops"],
          ["Consistent ratings over time", "\u2705 Reliability bonus", "Consistency rewarded (RH signal)"],
          ["Mixed good and bad ratings", "\u26A0 Reliability penalty", "Variance detected in history"],
          ["Rated by a low-trust agent", "\u26A0 Counts less", "WFS is requester-trust weighted"],
        ];
        return new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [c0, c1, c2],
          spacing: { before: 40, after: 40 },
          rows: [
            new TableRow({
              tableHeader: true,
              children: [
                headerCell("Situation", c0),
                headerCell("Effect", c1, true),
                headerCell("Why", c2),
              ]
            }),
            ...rows_data.map((r, i) => new TableRow({
              children: [
                dataCell(r[0], c0, i % 2 === 1, false, false),
                dataCell(r[1], c1, i % 2 === 1, true, false),
                dataCell(r[2], c2, i % 2 === 1, false, false),
              ]
            }))
          ]
        });
      })(),

      // Callout box
      calloutBox([
        "Volume without quality = low trust",
        "Quality without volume = moderate trust (capped at 40% until 3 real tasks)",
        "Volume + quality + consistency = high trust",
      ]),

      // ---- SECTION 2: Scaled Setup ----
      sectionHeader("Scaled Setup & Experiment Design"),
      bodyPara("Four automated phases ran against the live Vercel + Upstash Redis deployment:"),
      ...[
        "Phase 1 \u2014 Register 30 diverse agents across 7 categories (Medical, Code, Data, Legal, Research, Security, Translation)",
        "Phase 2 \u2014 Stress test: full delegate \u2192 submit-result \u2192 rate cycle, 3 rounds, 90 tasks total",
        "Phase 3 \u2014 Trust convergence: track 8 agents across 5 rating rounds to observe stabilisation",
        "Phase 4 \u2014 Resilience: trust gate blocking + anti-gaming attack + activity feed latency",
      ].map(text => new Paragraph({
        numbering: { reference: "bullets", level: 0 },
        spacing: { before: 0, after: 18 },
        children: [new TextRun({ text, size: halfPt(BASE_PT), font: FONT })]
      })),

      // ---- SECTION 3: Results ----
      sectionHeader("Results"),

      (() => {
        const c0 = 5040, c1 = 5040;
        const rows_data = [
          ["90/90 tasks succeeded", "0 failures, 0 timeouts"],
          ["Median full-cycle latency", "456ms (delegate + complete + rate)"],
          ["p95 latency", "507ms \u00B7 Max: 1,407ms (cold start) \u00B7 Min: 392ms"],
          ["Round trend", "R1=489ms \u2192 R3=459ms (stable, no degradation)"],
          ["Trust convergence", "8/8 agents: 20% \u2192 100% within 3 rounds, stable \u00B12%"],
          ["Trust gate", "Blocked FakeWeatherBot (23%) in 127ms \u2713"],
          ["Anti-gaming", "Circular ratings: 0% trust gain (capped at 40% until 3 real tasks) \u2713"],
          ["Activity feed", "Avg 1,866ms at 57 agents after O(N\u00D7M)\u2192O(M+N) fix \u2713"],
        ];
        return new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [c0, c1],
          rows: rows_data.map((r, i) => new TableRow({
            children: [
              dataCell(r[0], c0, i % 2 === 1, false, true),
              dataCell(r[1], c1, i % 2 === 1),
            ]
          }))
        });
      })(),

      // ---- SECTION 4: Failures & Bottlenecks ----
      sectionHeader("Failures & Bottlenecks Found"),

      (() => {
        const c0 = 2700, c1 = 4400, c2 = 2980;
        const rows_data = [
          ["ratings_count always 0", "to_dict() did not persist ratings list \u2014 lost on every cold start", "Fixed"],
          ["Activity feed timeout", "N\u00D7M Redis calls: all agents \u00D7 all tasks per agent", "Fixed \u2192 O(M+N)"],
          ["Stale reads post-registration", "Vercel caches /api/agents for 30s", "Fixed in script"],
          ["New agents blocked", "All start at 20%, below 30% gate", "Auto-seeded"],
          ["Trust spikes to 100%", "Simulated ratings uniformly high", "Known limitation"],
        ];
        return new Table({
          width: { size: CONTENT_W, type: WidthType.DXA },
          columnWidths: [c0, c1, c2],
          rows: [
            new TableRow({
              tableHeader: true,
              children: [
                headerCell("Issue", c0),
                headerCell("Root Cause", c1),
                headerCell("Status", c2),
              ]
            }),
            ...rows_data.map((r, i) => new TableRow({
              children: [
                dataCell(r[0], c0, i % 2 === 1, false, true),
                dataCell(r[1], c1, i % 2 === 1),
                dataCell(r[2], c2, i % 2 === 1, true),
              ]
            }))
          ]
        });
      })(),

      // ---- SECTION 5: What Was Added or Improved ----
      sectionHeader("What Was Added or Improved"),
      ...[
        "experiment_scale_test.py \u2014 4-phase automated test: registration, stress test with latency tracking, convergence, resilience",
        "api/activity.py \u2014 O(N\u00D7M) \u2192 O(M+N) Redis fix; activity load time: 10\u201330s \u2192 ~1.9s",
        "core/models.py \u2014 ratings and rating_weights added to to_dict() so trust history survives cold starts",
        "api/agents.py \u2014 Auto-backfill reconstructs ratings from task history on load",
        "public/app.js \u2014 Agent list sorted by trust desc; Uses badge uses ratings_count to resist gaming",
      ].map(text => new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        spacing: { before: 0, after: 18 },
        children: [new TextRun({ text, size: halfPt(BASE_PT), font: FONT })]
      })),

      // ---- SECTION 6: Key Takeaway ----
      sectionHeader("Key Takeaway"),
      new Paragraph({
        spacing: { before: 0, after: 35 },
        children: [new TextRun({
          text: "At 57 agents, the system\u2019s core properties held: the trust gate blocked unverified agents, anti-gaming rules prevented circular inflation, and median task latency stayed under 500ms. The primary fragility exposed at scale was Redis data persistence \u2014 trust scores depend on in-memory ratings lists that were silently discarded on cold starts. Infrastructure-level bugs, not algorithmic ones, are what break reputation systems at scale.",
          size: halfPt(BASE_PT),
          font: FONT,
          color: "111111",
        })]
      }),

    ]
  }]
});

// Write output
const outPath = path.join(__dirname, "HW8_Scale_Experiment_Report.docx");
Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(outPath, buffer);
  console.log("Written:", outPath);
  console.log("File size:", buffer.length, "bytes");
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
