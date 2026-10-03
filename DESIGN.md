---
name: Sergeant Pace
description: The recruit's individual counseling file. Copy-paper forms on an olive-drab desk, typed entries, red and blue stamp ink, a hazard plate for tripped safety rules.
colors:
  desk: "#2b3123"
  desk-hi: "#373f2c"
  desk-line: "#4a5339"
  desk-text: "#e1e4d2"
  desk-dim: "#a9af95"
  paper: "#e9ece3"
  paper-shade: "#daded1"
  paper-field: "#f4f6ee"
  rule-black: "#161a11"
  caption: "#4a5240"
  typed-blue-black: "#18223d"
  stamp-red: "#b92d1b"
  stamp-blue: "#25458c"
  hazard-amber: "#f0b400"
  highlight-amber-tint: "#f1e3b0"
  done-green: "#b8d98a"
typography:
  display:
    fontFamily: "Big Shoulders Stencil Display, Arial Narrow, sans-serif"
    fontSize: "clamp(44px, 6.6vw, 96px)"
    fontWeight: 800
    lineHeight: 0.9
    letterSpacing: "0"
  countdown:
    fontFamily: "Big Shoulders Stencil Display, Arial Narrow, sans-serif"
    fontSize: "clamp(100px, min(17vw, 23vh), 220px)"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "0"
    fontFeature: "tabular-nums"
  headline:
    fontFamily: "Big Shoulders Stencil Display, Arial Narrow, sans-serif"
    fontSize: "clamp(26px, 2.6vw, 34px)"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "0.05em"
  title:
    fontFamily: "Big Shoulders Stencil Display, Arial Narrow, sans-serif"
    fontSize: "clamp(22px, 2.1vw, 28px)"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "0.04em"
  body:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "clamp(20px, 1.9vw, 26px)"
    fontWeight: 500
    lineHeight: 1.35
  typed:
    fontFamily: "Courier Prime, Courier New, monospace"
    fontSize: "clamp(18px, 1.6vw, 22px)"
    fontWeight: 700
    lineHeight: 1.35
  label:
    fontFamily: "Archivo, Helvetica Neue, Arial, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.1em"
    fontVariation: "font-stretch 72%; uppercase"
rounded:
  none: "0px"
spacing:
  xs: "8px"
  sm: "14px"
  md: "18px"
  lg: "24px"
  xl: "clamp(20px, 3.4vw, 44px)"
components:
  button-primary:
    backgroundColor: "{colors.stamp-blue}"
    textColor: "{colors.paper}"
    typography: "{typography.title}"
    rounded: "{rounded.none}"
    padding: "18px 30px"
  button-plain:
    backgroundColor: "transparent"
    textColor: "{colors.rule-black}"
    rounded: "{rounded.none}"
    padding: "18px 30px"
  tab-desk:
    backgroundColor: "transparent"
    textColor: "{colors.desk-text}"
    rounded: "{rounded.none}"
    padding: "11px 16px"
  sheet:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.rule-black}"
    rounded: "{rounded.none}"
    padding: "clamp(20px, 3.4vw, 44px) clamp(18px, 3.4vw, 48px)"
  field:
    backgroundColor: "{colors.paper-field}"
    textColor: "{colors.typed-blue-black}"
    typography: "{typography.typed}"
    rounded: "{rounded.none}"
    padding: "10px 16px 12px"
  checkbox:
    backgroundColor: "#f3f5ec"
    rounded: "{rounded.none}"
    size: "44px"
  stamp-red:
    textColor: "{colors.stamp-red}"
    typography: "{typography.headline}"
    rounded: "{rounded.none}"
    padding: "6px 18px 8px"
  stamp-blue:
    textColor: "{colors.stamp-blue}"
    typography: "{typography.headline}"
    rounded: "{rounded.none}"
    padding: "6px 18px 8px"
  hazard-plate:
    backgroundColor: "{colors.hazard-amber}"
    textColor: "{colors.rule-black}"
    typography: "{typography.headline}"
    rounded: "{rounded.none}"
  action-bar:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.rule-black}"
    rounded: "{rounded.none}"
    padding: "12px 24px 14px"
---

# Design System: Sergeant Pace

## Overview

**Creative North Star: "The Recruit's Counseling File"**

Every run ends in a developmental counseling record the agent conducts on paper, in public: Facts typed in, Assessment boxes inked, a Plan of Action decided and stamped, the old plan struck through and the new one written beneath. The ground is an olive-drab desk; everything the agent says or decides lives on cool copy-paper forms with 1px-to-3px black rules and ruled cells. It reads at a glance and is recognizable with all copy removed.

The build is square, flat-ruled and heavy. There are no radii, no cards-with-avatars, no chat bubbles. Depth comes from paper lying on a desk (soft cast shadows), not from decoration. Motion is the file being filled out: typed, inked, stamped. The craft is in the stencil headings, the typewriter entries and the rough-edged stamp ink.

**Key Characteristics:**
- Dark desk, light paper: two surfaces only (desk ground, form paper); the live run sits on the desk itself.
- Three voices: stencil (headings, stamps, form number), narrow grotesque caps (form captions), typewriter (everything the recruit or agent "entered").
- Ink colour is meaning: red means failed, stop, refused, warning, denied; blue means cleared, advanced, enlisted.
- Zero border radius everywhere.
- Authored procedural textures only (SVG fibers, grain, ink filter); no raster.

## Colors

A restrained olive and paper palette with two stamp inks and one hazard amber; each chromatic colour carries a fixed meaning.

### Primary
- **Stamp Blue** (#25458c): Approved ink. Primary button fill, run segments in the timeline, ticked boxes and circles, `.ok` assessment headings, completed qualification cells, sheet focus ring. Means cleared, advanced, enlisted.
- **Stamp Red** (#b92d1b): Refusal ink. Failed assessment headings, struck-through old plan values, red checks, the red stamp. Means failed, stop, refused, warning, denied.

### Secondary
- **Hazard Amber** (#f0b400): The hazard plate on any tripped safety rule (with SVG diagonal stripe ends), the live-run needle, the RUN phase word on the desk, text selection, and the focus ring on the desk.

### Neutral
- **Desk Olive** (#2b3123): page ground, with desk-hi (#373f2c) hover and a radial vignette (#3b432f centre to #1f241a edge); desk-line (#4a5339) borders; desk-text (#e1e4d2) and desk-dim (#a9af95) type on the desk.
- **Copy Paper** (#e9ece3): form surface, with paper-shade (#daded1) for hover, warm-up and cool-down fills, and table heads; paper-field (#f4f6ee) for input cells.
- **Rule Black** (#161a11): all rules, borders and printed type on paper.
- **Caption Grey-Olive** (#4a5240): form captions, secondary printed text.
- **Typed Blue-Black** (#18223d): every typed value and entry, always in Courier Prime bold.
- **Highlight Tint** (#f1e3b0): the "next" qualification and "current" week cell. Done Green (#b8d98a) is used only for the finished phase word on the desk.

### Named Rules
**The Ink Means Rule.** Red and blue are never decorative. Red is only for failure, stop, refusal, warning, denial; blue only for approval, advance, enlistment. If a state is neither, use rule black.
**The Hazard Plate Rule.** A tripped safety rule always appears as the amber plate with striped end caps, never as a red alert or a toast.
**The Not-Colour-Alone Rule.** Meaning pairs colour with a second channel: stamp text, strike-through, hatch pattern, label.

## Typography

**Display Font:** Big Shoulders Stencil Display (with Arial Narrow, sans-serif), variable 400-900, self-hosted
**Body Font:** Archivo (with Helvetica Neue, Arial, sans-serif), variable weight and width (62-125%), self-hosted
**Label/Mono Font:** Courier Prime 400 and 700 (with Courier New, monospace), self-hosted

**Character:** Stencil is the issuing authority, Archivo condensed caps is the printed form, Courier is the hand that fills it. Body size is large (18px base) because the file is screen-recorded and read at a glance.

### Hierarchy
- **Display** (800, clamp(44px, 6.6vw, 96px), 0.9): the question or order headline, uppercase, balanced wrap. The job title uses clamp(40px, 5.6vw, 88px).
- **Countdown** (900, clamp(100px, min(17vw, 23vh), 220px), 1, tabular): the live-run numeral. A deliberate exception above the usual display ceiling; the height-aware clamp keeps it inside the viewport.
- **Headline** (800, clamp(26px, 2.6vw, 34px), 1, 0.05em): block headings (Facts, Assessment, Plan of Action, Remarks), stamps, buttons (24-32px), phase word (40-80px, 0.06em).
- **Title** (800, clamp(22px, 2.1vw, 28px), 1.05, 0.04em): assessment line headings, drawer section heads (24px), form number (24px, 0.06em).
- **Body** (Archivo 500, clamp(20px, 1.9vw, 26px), 1.35): the sergeant's remarks and the lead sentence, capped near 60-62ch.
- **Typed** (Courier Prime 700, clamp(18px, 1.6vw, 22px), 1.35): all entered values; large input values scale to 34-56px, stepper values 56px.
- **Label** (Archivo 600, 13px, 0.1em, uppercase, font-stretch 72-80%): form captions, legend, tab and link text (14-15px).

### Named Rules
**The Typed Is Entered Rule.** Courier Prime bold in Typed Blue-Black is reserved for values that were entered into the file. Printed text never uses it.
**The Stencil Is Authority Rule.** Stencil is uppercase, for headings, stamps, buttons and the form number only; it never sets sentences.

## Layout

A single wide sheet (max-width 1200px, centred) on the desk under a sticky 12px-padded top bar. Page padding is fluid, clamp(12px, 3vw, 40px). The counseling record is a three-column grid (1fr, 1.15fr, 1.1fr) separated by 2px rules, with small paper-coloured notch arrows between blocks, then full-width Remarks, a plan-diff table and a pinned bottom action bar (sticky, 3px top rule). The order view is a 1.5fr/1fr two-column ruled box beneath the timeline. The live run is not on paper: it is centred on the desk (max 1100px) with a paper "drill" strip under the numeral.

Spacing rhythm is 8, 14, 18, 24 inside forms and clamp(20px, 3vw, 36px) between major bands. Rows are separated by 1px dotted rules (#6a7260), not boxes. Touch targets are large: 44px checkboxes, 64-96px report ticks, 84px stepper buttons.

Breakpoints: at 900px the counseling grid, order columns, remarks and diff rows stack to one column; at 620px the form number and file line are hidden, choices and fields go single column, buttons go full width, the hazard plate end caps shrink to 28px, and the action bar's "next" hint is dropped while the bar stays pinned.

## Elevation & Depth

Depth is paper on a desk. Sheets sit above the desk with a layered soft shadow (a hairline inset highlight, a short 3px/4px contact shadow, and a long 34px, -24px-spread drop). Content within a sheet is flat and ruled; there is no per-element elevation.

### Shadow Vocabulary
- **Sheet** (`0 1px 0 rgba(255,255,255,.5) inset, 0 3px 4px rgba(0,0,0,.35), 0 34px 60px -24px rgba(0,0,0,.75)`): the form on the desk.
- **Drill strip** (`0 3px 4px rgba(0,0,0,.35), 0 26px 50px -24px rgba(0,0,0,.7)`): the paper under the live numeral.
- **Action bar** (`0 -16px 26px -16px rgba(0,0,0,.4)`): the pinned bar lifting off the sheet body.
- **File drawer** (`-2px 0 0 rgba(0,0,0,.5), -30px 0 60px rgba(0,0,0,.5)`) over a 60% desk-black scrim.

### Named Rules
**The Paper On Desk Rule.** Only whole sheets and the drawer cast shadows, and they are soft and offset. Inner controls take rules, never shadows.

## Shapes

Square. Every box, button, field, stamp and plate has 0 radius. Form language is rule-weights: 1px for dotted rows and segment dividers, 2px for cells, fields and column splits, 3px for the header underline, timeline frame, stepper, scale and action-bar top rule, 4px double for stamps. Stamps are rotated -7deg with a rough, uneven-pressure ink filter and multiply blending. Checks and circles are hand-drawn round-capped SVG strokes that overshoot their box. The insignia is a drawn three-chevron mark; no emoji or glyph icons.

## Components

### Buttons
- **Shape:** square, no radius.
- **Primary:** Stamp Blue fill, Copy Paper stencil text 24-32px uppercase, padding 18px 30px (12px 26px in the action bar). Hover brightens 1.15; active drops 2px; disabled 40% opacity.
- **Plain:** transparent with a 2px rule border; hover fills paper-shade. On the desk it inverts to desk-text and desk-dim.
- **Link / Tab:** underlined 15px caption caps for tertiary actions; the desk tab is a 1px desk-line outlined caps button. Destructive reset is a two-tap link ("Tap again to wipe the file", disarms after 4s); native confirm dialogs are never used.

### Fields and Checkboxes
- **Field:** 2px rule border, paper-field fill, caption above, large Courier Prime bold value. Focus is a 3px Stamp Blue outline offset 3px (amber on the desk). Multi-line notes use a ruled-line background in Courier 22px/36px.
- **Checkbox:** 44px square, 3px rule border; ticked by a hand-drawn stroke that animates in (red or blue ink). Report ticks scale to 64-96px; the 1-10 scale is a ruled 10-cell strip with an inked circle; the stepper is flanked 84px buttons.

### Stamps
Stencil word in a 4px double border, red or blue by the Ink Means Rule, with an optional small caption citing the rule that triggered it. It slams in with a 2.3x-to-1 scale over 0.3s and settles at 0.95 opacity.

### Hazard Plate
Amber bar with 3px rule bottom, a stencil message centred, and diagonal-striped end caps (an SVG 24px stripe pattern, 76px wide, 28px on mobile). It drops in 14px on arrival. It appears on any tripped safety rule.

### Timeline Bar (signature)
The march bar encodes segments by fill and pattern, never colour alone: run is a solid Stamp Blue fill with paper text, walk is an SVG diagonal hatch (12px tile, 38% rule-black), warm-up and cool-down are plain paper-shade tint. A ruler above ticks minutes in tabular Archivo; a legend repeats the three swatches. In the live run an amber 4px needle sweeps it.

### Counseling Block and Action Bar
Blocks are ruled columns headed by a stencil title; facts are typed rows over dotted rules with a blinking block caret while "typing". Assessment lines pair a 44px box with a stencil verdict (red for bad, blue for ok). The Plan of Action lists mode boxes (chosen one in rule black, others in caption). The old plan value is red strike-through (3px), the new value typed beneath. The bottom action bar is pinned to the sheet's bottom edge on the counseling sheet so the single next action is always reachable.

### File Drawer
560px paper panel sliding from the right with a sticky form header, qualification cells (done = blue fill, next = highlight tint), a progress table with caption-cap heads, and Courier entries.

### Motion
One easing, `cubic-bezier(0.16, 1, 0.3, 1)`. Views arrive with a 0.5s 14px rise; sheets "thunk" 3px when stamped. Under `prefers-reduced-motion` animation and transition durations collapse to near zero and the JS skips the typed, inked and stamped sequence, showing every entry immediately.

## Do's and Don'ts

### Do:
- **Do** keep every surface either desk olive (#2b3123) or copy paper (#e9ece3) with 1-3px rule-black lines.
- **Do** set every entered value in Courier Prime 700 Typed Blue-Black and every heading, stamp and button in stencil caps.
- **Do** back red/blue meaning with a second channel (stamp word, strike-through, hatch, label).
- **Do** show any tripped safety rule as the amber hazard plate citing the rule.
- **Do** keep the countdown as the only numeral above the display ceiling, sized with the height-aware clamp (max 220px).
- **Do** use two-tap confirmation for destructive actions and keep a pinned bottom action bar on the counseling sheet.
- **Do** preserve the reduced-motion path: all entries visible at once, no typed, inked or stamped sequence.

### Don't:
- **Don't** use red or blue as decoration; their meaning is fixed.
- **Don't** add border radius, gradient buttons, per-element drop shadows, avatars or chat bubbles.
- **Don't** use native confirm, alert or prompt dialogs.
- **Don't** set timeline segments by colour alone, or add emoji or glyph icons; use drawn SVG marks.
- **Don't** raster any texture; paper, grain and ink stay authored SVG.
- **Don't** set sentences in stencil or printed text in Courier.

*Not canonized (build carries them as defects):* a few captions are below the 13px floor (12px qualification labels and progress table heads), and `.counsel-foot .next` has stray indentation in the stylesheet. The file also relies on an accent text colour (#262d1d) for the lead sentence that is not a named token.
