# LLM Council Transcript

- Invocation timestamp: 2026-09-02T23:42:46Z
- Mode: Standard (auto-selected — default)
- Decision Science: not run
- Question SHA-1 prefix: `dc47c28e`

## Framed question

DECISION: Should a three-person team adopt the revised Temporal Scene Intelligence architecture for a six-day AI Video Intelligence for Warehouse Handling hackathon, and what should be kept, simplified, or removed to maximize technical differentiation without jeopardizing delivery?

CONTEXT: Workspace scan: no project context found. Council proceeds with user-provided context only. The repository is empty. The team has five build days followed by one security/testing/polish day. The revised architecture proposes validated UUID-based video ingestion; a first-pass detector/tracker; track histories; a Temporal Scene Graph with relationships such as NEAR, SUPPORTED_BY, INSIDE, MOVING and OVERHANGS; cheap candidate generators followed by behavior-specific higher-FPS/high-resolution verification; five behavior categories across ten scenarios; configuration-driven Python state machines with YAML thresholds; versioned deterministic risk policies; a camera calibration/zone UI; a durable SQLite job queue with leases and heartbeats; Pydantic/OpenAPI as the single API-contract source with a generated TypeScript client; a grounded OpenAI Responses API assistant with allowlisted tools and no generated SQL; reproducible run/evidence manifests; event-level evaluation; Next.js frontend, FastAPI API, Python vision worker, SQLite and protected local media. Proposed differentiators include two-pass inference, explainable rule traces, reproducibility, calibration, human review and optional privacy blurring. Multi-camera ReID, live CCTV, WMS integration, digital twin, Kubernetes and autonomous retraining are out of scope.

STAKES: Missing the deadline or presenting a fragile demo would undermine the submission. A generic YOLO dashboard may not differentiate, while an over-engineered scene-graph platform may fail to integrate in time. Privacy, false claims about physical risk, licensing and reproducibility affect credibility.

OPTIONS: (1) build the full revised architecture; (2) revert to a simpler YOLO-plus-rules dashboard; (3) use a stage-gated hybrid that implements only the highest-leverage differentiators behind fallback paths.

PRIOR: No related council run found.

BIAS FLAGS: Planning fallacy — compare options using conservative effort estimates, explicit dependencies, and daily kill criteria. Anchoring — define judging outcomes first and independently derive the minimum architecture that proves them. IKEA effect — retain features only when expected judging value exceeds implementation and integration risk. Narrative fallacy — treat differentiation claims as hypotheses requiring a judge-facing proof or benchmark.

## Bias audit

BIAS: Planning fallacy  
SIGNAL: A three-person team has five build days to integrate many novel components plus ten scenarios and a polished demo.  
REFRAME: Compare options using conservative effort estimates, explicit dependencies, and daily kill criteria.

BIAS: Anchoring  
SIGNAL: The unusually detailed revised architecture may anchor discussion around trimming it rather than selecting the smallest winning design from first principles.  
REFRAME: Define judging outcomes first, then independently derive the minimum architecture that proves them.

BIAS: IKEA effect  
SIGNAL: The revised design’s sophistication may be valued partly because the team conceived it, despite limited evidence that judges reward each component.  
REFRAME: Retain features only when their expected judging value exceeds their implementation and integration risk.

BIAS: Narrative fallacy  
SIGNAL: The framing assumes a generic dashboard will not differentiate and a scene graph will, without stated judging evidence.  
REFRAME: Treat differentiation claims as hypotheses requiring a judge-facing proof or benchmark.

## Anonymization map

- Advisor A → Expansionist
- Advisor B → First Principles
- Advisor C → Red Team
- Advisor D → Executor
- Advisor E → Outsider

The permutation was seeded from the first four hex digits of the framed-question SHA-1.

## Advisor responses

### Red Team

1. THE FAILURE MODE

On demo day, the system has impressive architecture diagrams but an unreliable end-to-end path. Several scenarios fail because tracking IDs fragment, calibration is inconsistent, verification workers lag, and state-machine thresholds were never tuned. The assistant explains incomplete evidence, undermining credibility rather than adding polish.

2. THE ROOT CAUSE

The decisive mistake was committing on day one to the full revised architecture instead of freezing a stage-gated hybrid with a mandatory working baseline. The team treated components as individually feasible while ignoring integration, tuning, test-data, and demo-rehearsal costs. Three people spent five days building infrastructure instead of proving ten scenarios.

3. THE MISSED SIGNAL

By the end of day two, there was no deterministic upload-to-event-to-evidence vertical slice across representative scenarios. That should have triggered immediate scope cuts. Instead, visible progress on schemas, queues, graph relations, generated clients, and UI scaffolding created false confidence despite no judge-facing proof of detection quality or system reliability.

4. THE ALTERNATIVE

Build one boring vertical slice first: UUID ingestion, detector/tracker, track histories, three high-value behaviors, deterministic risk rules with readable traces, evidence clips, and a simple dashboard. Keep two-pass verification only for one behavior where it produces a measurable precision gain. Represent temporal relations as internal derived features, not a general graph platform. Use SQLite simply; hand-write the small client; make calibration preset-driven; restrict the assistant to summarizing stored event records. Add more behaviors only after the ten demo scenarios pass repeatedly by day four.

=== CONFIDENCE ===  
confidence: high  
assumptions:
- The team starts without reusable code.
- Demo reliability outweighs architectural breadth.
- Pre-recorded scenarios are permitted.

what_would_change_my_mind:
- Existing production-ready components cover most integrations.
- Judging explicitly rewards architectural completeness over execution.

unknowns: Team skill split, compute hardware, dataset readiness, and judging rubric.

### First Principles

REFRAMING A: Discard “architectural completeness creates differentiation” → Adopt the stage-gated hybrid. Differentiation comes from one visibly convincing temporal behavior, verified by a second pass and backed by inspectable evidence—not from implementing every subsystem. Keep secure ingestion, tracking histories, one thin temporal relation model, candidate→verification inference, deterministic risk policy, and evidence manifests. Simplify to two behaviors and three curated scenarios.

REFRAMING B: Discard “all production-grade foundations are equally necessary for a hackathon” → Build the simplest credible vertical slice. Keep UUID filenames, basic upload validation, SQLite, explicit job states, and allowlisted assistant tools. Simplify leases to a single-worker recoverable queue, OpenAPI generation to a late-stage convenience, and calibration UI to editable polygons plus thresholds. Remove privacy blur, generalized state-machine authoring, autonomous assistant behavior, and elaborate human-review workflows unless the core demo is already stable.

REFRAMING C: Discard “scope should be selected feature-by-feature” → Allocate work by failure containment. Establish a baseline YOLO-plus-rules demo by day two; add temporal verification only behind interfaces with deterministic fallbacks. Freeze scope after day three. Every differentiator must be removable without breaking ingestion, analysis, evidence playback, or evaluation.

STRONGEST: C — It preserves option value under extreme schedule uncertainty. The irreducible product is a repeatable demonstration: ingest a video, identify a risky event, explain it with time-linked evidence, and reproduce the result. Baseline-first sequencing prevents the sophisticated path from becoming the only path. The highest-leverage additions are two-pass verification, concise reasoning traces, versioned policies, and reproducible manifests; these jointly support technical novelty and credibility.

RUNNER-UP: A — It gives the clearest differentiated story, but still risks overbuilding abstractions before one behavior works reliably.

=== CONFIDENCE ===  
confidence: high  
assumptions:
- The demo can use curated local videos.
- Judges reward working evidence more than architectural breadth.
- Models and licenses are selectable immediately.

what_would_change_my_mind:
- Mandatory coverage of all ten scenarios.
- Existing reusable implementations for most “full” components.

unknowns: Team skill split, available GPU, target video quality, judging rubric.

### Expansionist

OPTION X: Proof-carrying vertical slice — upside: H / effort delta: L  
Implement one “hero” warehouse behavior end to end with three scenario variants. Retain two-pass verification, compact track histories, deterministic policy, evidence clips, reasoning traces, and event-level evaluation. Represent temporal state as ordinary SQLite tables rather than a general Scene Graph.

OPTION Y: Replay-first temporal lab — upside: H / effort delta: L  
Make recorded detections/tracks the primary deterministic input, with live detector/tracker integration as a replaceable adapter. This enables reproducible demos, fast calibration, failure injection, and credible evaluation even if GPU inference fails. Clearly label replay versus live operation.

OPTION Z: Evidence-review workstation — upside: M / effort delta: M  
Center the product on ranked incident review: event timeline, verification frames, thresholds, reviewer disposition, and privacy blur. Treat the grounded assistant as an optional narrator over structured evidence, not a core reasoning component.

DOMINANT: X — It preserves the architecture’s most defensible differentiation—temporal reasoning, selective verification, traceability, and measurable performance—while removing breadth-driven integration risk. One deeply demonstrated behavior will usually outperform five partially reliable behaviors.

WHY IT DOMINATES THE USER’S OPTIONS: Compared with the full architecture, X removes the generalized Scene Graph, ten-scenario matrix, broad state-machine framework, assistant dependency, and optional blur from the critical path. Compared with YOLO-plus-rules, it still demonstrates genuine temporal intelligence. Compared with the stage-gated hybrid, it defines a sharper product boundary rather than leaving scope gates vulnerable to planning fallacy. Pair X with Y as the delivery fallback.

=== CONFIDENCE ===  
confidence: high  
assumptions:
- Judges reward demonstrable depth and evidence over feature count.
- Representative warehouse footage can be obtained early.
- One behavior can be evaluated with meaningful positive and negative cases.

what_would_change_my_mind:
- Mandatory judging criteria require all five behaviors.
- A mature internal Scene Graph implementation already exists.

unknowns: GPU availability, team skill split, footage rights, and target behavior complexity.

### Outsider

FIELD: Experimental flight testing — because novel aircraft are not validated by attempting the full flight envelope on day one. Teams establish a stable configuration, instrument it, expand capability incrementally, and preserve abort modes.

NAIVE READ: This appears to be a choice among “ambitious architecture,” “basic dashboard,” and “hybrid.” But why is it a single architecture decision at all? The real decision is which capabilities earn permission to enter the demo after proving they do not endanger the stable flight configuration.

BUBBLE SPOTS: Software insiders may assume that generalized abstractions demonstrate sophistication, that ten named scenarios imply coverage, and that production-shaped infrastructure creates credibility. Judges cannot observe most of that. They can observe whether one upload completes, one event is correctly localized, the explanation matches visible evidence, and rerunning produces the same result. Configurable state machines, generated clients, leases, assistants, and privacy blur each sound modest in isolation; together they create integration surfaces whose failure probability compounds.

CROSS-DOMAIN INSIGHT: Use flight-envelope expansion. By day two, establish the “taxi-test” baseline: validated ingestion → detector/tracker → deterministic rule → evidence playback. Freeze that as the always-working fallback. Then admit differentiators one at a time through explicit gates: first temporal track histories, then cheap-candidate/targeted-verification inference, then manifests and event-level evaluation. Keep simple versioned risk policies and minimal polygon calibration. Reduce scope to two excellent behaviors across three curated scenarios. Simplify SQLite to a recoverable single-worker queue and relations to only those needed by chosen behaviors. Remove the grounded assistant, generalized rule authoring, privacy blur, and remaining scenario breadth unless the instrumented baseline remains green after integration and rehearsal.

=== CONFIDENCE ===  
confidence: high  
assumptions:
- A curated-video demo is acceptable.
- Architecture internals score only when visibly evidenced.
- Components can be isolated behind fallback interfaces.

what_would_change_my_mind:
- Judging explicitly rewards breadth or assistant interaction.
- The team already owns reusable implementations.

unknowns: Team skill allocation, GPU availability, rubric, and sample-video difficulty.

### Executor

1. OODA STAGE: Orient → Decide. Appropriate only if Observe/Orient is time-boxed to the first half-day: confirm footage, hardware throughput, and one behavior’s measurable acceptance criteria. The team should then commit to a hero-slice hybrid; continued architecture design becomes deadline risk.

2. RICE SCORING

| Option | Reach | Impact | Confidence | Effort (person-weeks) | Approx. score |
|---|---:|---:|---:|---:|---:|
| Full revised architecture | XL | H | 40% | 7.0 | 0.46 |
| YOLO-plus-rules | L | M | 90% | 2.0 | 1.35 |
| Stage-gated hybrid | XL | H | 75% | 3.5 | 1.71 |
| Missing: one proof-carrying hero behavior | L | H | 85% | 2.5 | **2.04** |

Adopt the hybrid, but constrain it to the missing hero-slice option. Keep validated ingestion, tracking histories, cheap candidate generation plus targeted verification, deterministic risk output, evidence/reason traces, manifests, and event-level tests. Simplify the Scene Graph into SQLite-backed track/event records; hard-code one or two state machines before generalizing; make calibration a small threshold panel; use polling jobs rather than elaborate leasing unless parallel workers are proven necessary. Remove the grounded assistant, generated-client pipeline, privacy blur, and four non-hero behaviors from the critical path.

Likely breakpoints are detector IDs, codec ingestion, verification latency, and demo data mismatch. Dependencies must be frozen by Day 1; a deterministic replay path should protect the demo.

3. DATA COMPLETENESS CHECK

- STATUS: DRAFT — BLOCKED ON target hardware and measured FPS.
- STATUS: DRAFT — BLOCKED ON licensed representative footage.
- STATUS: DRAFT — BLOCKED ON behavior definitions and labeled acceptance set.

=== CONFIDENCE ===  
confidence: high  
assumptions:
- Approximately 3.6 person-weeks of nominal capacity exists.
- Judges value validated temporal depth over scenario count.

what_would_change_my_mind:
- Existing reusable components cut full-option effort below four person-weeks.
- Judging mandates broad behavior coverage.

unknowns: hardware throughput; footage availability/licensing; ground-truth acceptance criteria.

## Peer reviews

### Reviewer 1

1. STRONGEST: E. It gives the clearest operational stage-gated hybrid: freeze a working Day-2 baseline, admit features incrementally, preserve replay fallback, and sharply constrain demo scope.

2. EXPLOITABLE WEAKNESS: Its gates lack measurable entry criteria—latency, precision/recall, track stability, and reproducibility thresholds—so optimism could still override evidence.

3. COLLECTIVE MISS: No response defines the audit-day plan, especially adversarial upload testing, dependency/model-license review, privacy handling, and reproducibility verification.

CONSENSUS STRENGTH: 5

### Reviewer 2

1. STRONGEST: D. It converts the choice into an actionable hero-slice hybrid, clearly separating critical-path capabilities from deferrable ones while preserving replay fallback, evidence, traces, manifests, and event tests.

2. EXPLOITABLE WEAKNESS: Its numerical priority scores imply rigor without explaining criteria, weights, or sensitivity; the apparent precision could anchor the team rather than improve the decision.

3. COLLECTIVE MISS: None reserves the sixth day with a concrete audit protocol—security/privacy review, dependency and model-license checks, failure-mode testing, reproducibility verification, and explicit ship/no-ship criteria.

CONSENSUS STRENGTH: 5

### Reviewer 3

1. STRONGEST: D. It makes the sharpest scope decision: a stage-gated hybrid reduced to one proof-carrying behavior, while explicitly separating critical-path features from cuts and preserving deterministic replay as a demo fallback.

2. EXPLOITABLE WEAKNESS: D’s numerical scores are unsupported pseudo-precision. Without stated weights, measurements, or acceptance thresholds, “2.04 versus 1.71” adds confidence theater rather than decision evidence. It also lacks concrete gates for admitting verification or additional behaviors.

3. COLLECTIVE MISS: None meaningfully plans the dedicated audit day. The recommendation should reserve it for a clean-room reproducibility run, dependency/license review, upload and assistant security checks, manifest validation, event-level regression tests, and rollback verification—with build scope frozen beforehand.

CONSENSUS STRENGTH: 5

### Reviewer 4

1. STRONGEST: E. Its flight-test approach converts ambition into reversible, evidence-based gates: secure a Day-2 baseline, admit advanced features only after measurable success, narrow demonstrations, and preserve a replay fallback.

2. EXPLOITABLE WEAKNESS: Freezing the Day-2 baseline may reinforce anchoring. Without predefined pass/fail metrics, the team could preserve an inadequate architecture and subjectively label favored additions “green.”

3. COLLECTIVE MISS: No response budgets explicitly for obtaining representative footage, producing ground-truth annotations, and defining quantitative acceptance thresholds. Without that evaluation substrate, “measurable improvement,” calibration, and selective verification remain vulnerable to curated-demo overfitting.

CONSENSUS STRENGTH: 5

### Reviewer 5

1. STRONGEST: D. It converts the hybrid into an executable five-day scope: one hero behavior, a deliberately simplified architecture, explicit cuts from the critical path, and replay as a demo-continuity fallback. Flagging hardware, footage, and acceptance criteria also exposes the unknowns most likely to invalidate the schedule.

2. EXPLOITABLE WEAKNESS: D does not define quantitative gates for retaining verification or judging the hero behavior. “Priority scoring” can therefore rationalize preferred features after the fact, while replay may conceal poor live-system reliability.

3. COLLECTIVE MISS: No advisor specifies a representative target-footage test set and measurable acceptance contract—such as track continuity, event precision/recall, end-to-end latency, and recovery behavior—validated on the actual deployment hardware. Without that, Day-2 baselines and later gates remain subjective, and curated demos can manufacture apparent differentiation.

CONSENSUS STRENGTH: 4

Consensus-strength average: 4.8/5. Forced debate triggered.

## Debate round

### Prosecutor

The consensus is a sophisticated way to build neither a reliable MVP nor a compelling differentiator. In five build days, “proof-carrying” gates, targeted reprocessing, track histories, reasoning traces, policy versioning, manifests, and event-level evaluation are still a distributed integration project disguised as restraint. Freezing a Day-2 baseline creates an architectural tax: the team either hardens throwaway interfaces prematurely or keeps reopening the “frozen” slice as later stages expose incompatible data needs.

The worst outcome is especially plausible: tracking fails on real footage, so histories and temporal verification become untrustworthy; quantitative gates then correctly reject the very features meant to differentiate the demo. The team arrives with three brittle behaviors, an unimpressive dashboard, and evaluation numbers that advertise failure—while a simple YOLO-plus-rules product could have delivered polished UX, broad scenarios, predictable latency, and rehearsed footage. “Replay fallback” worsens credibility if judges notice it is not live.

The hidden assumption is not merely curated footage; it is that judges value architectural evidence they cannot inspect over visible capability they can immediately test. Licensing, hardware, and representative clips remain unresolved, so the proposed gates may optimize against synthetic conditions and confer false confidence.

The single confirming piece of evidence: by the end of Day 1, ID-switch rate on licensed representative footage exceeds the maximum compatible with any chosen temporal behavior.

### Defender

1. **CONCEDE:** “Proof-carrying” can become a distributed-systems trap if histories, manifests, policies, and reprocessing are implemented as independent services or unstable APIs. Day-1 tracking quality on representative, licensed footage is the decisive dependency.

2. **REBUT:** That risk supports stage-gating, not a YOLO-only pivot. Implement the baseline as one deterministic process with append-only event records; treat traces, policy versions, and manifests as fields in that record—not separate platforms. No gate passes, no integration expands. If tracking misses its Day-1 threshold, freeze the baseline and present reliable detection scenarios rather than forcing temporal features.

3. **COUNTER-EVIDENCE:** Five build days favor one vertically complete flow over broad scenarios: upload → event → timestamped evidence → replay. A YOLO dashboard can show boxes, but cannot credibly demonstrate duration, sequence, or revisit behavior without track history. Evidence is not invisible when surfaced beside each event: clip, boxes, timestamps, policy version, and decision trace. Replay is legitimate when explicitly labeled as a deterministic fallback using the same stored artifacts and evaluation path.

4. **REMAINING RISK:** Measure ID-switches, track fragmentation, event precision/recall, and p95 latency on licensed representative clips by end of Day 1. Predeclare kill thresholds and fallback behavior; prohibit new interfaces after Day 2.

## Chairman-Consensus verdict

Council confidence: high (5/5 high, 0/5 medium, 0/5 low)  
Dominant assumption: Demo reliability matters more than architectural breadth, and every differentiator must earn inclusion through measurable stage gates.  
Breakers: Unacceptable tracking fragmentation or ID-switch rates on representative licensed footage by end of Day 1; failure to demonstrate a repeatable upload→event→evidence path on target hardware by end of Day 2.

## Where the council agrees

- Adopt a stage-gated hybrid, not the full revised architecture and not a permanently bare YOLO dashboard. Red Team, First Principles, Outsider, and Executor all prioritize an always-working baseline before admitting differentiators.
- Establish the baseline by Day 2 and freeze expansion after Day 3. Red Team, First Principles, Outsider, and the debate Defender support explicit cut points that protect the final testing day.
- Retain validated UUID ingestion, compact track histories, deterministic risk logic, evidence clips/timestamps, decision traces, manifests, and event-level tests. Red Team, First Principles, Expansionist, and Executor identify these as the highest-leverage sources of credibility.
- Keep targeted high-FPS verification only if measured results justify it and place it behind a removable boundary. Red Team, First Principles, Expansionist, Outsider, and Executor converge on selective—not universal—two-pass processing.
- Reduce semantic scope aggressively: approximately two or three behaviors, a few scenarios, and ideally one polished “hero” behavior with variants. Red Team, Expansionist, Outsider, and Executor prefer depth and proof over the proposed five-behavior/ten-scenario breadth.
- Avoid premature platform engineering. Expansionist, Outsider, Executor, and the debate Defender favor one deterministic process, simple SQLite polling, append-only event records, and derived relation features instead of a generalized graph or distributed verifier.
- Preserve a clearly labeled replay mode as a fallback and development harness, while keeping live processing as the credibility target. Expansionist, Executor, Outsider, and the Defender support replay when it is transparent.

## Where the council clashes

The main clash is between a broad, visually impressive YOLO-plus-rules demo and a narrower proof-carrying hybrid. The simple-demo side correctly warns that tracking, verification, manifests, traces, and evaluation can still become an integration project, and that judges may reward visible breadth more than architectural rigor. The hybrid side is more persuasive because it contains that risk through a frozen baseline, removable enhancements, and a single-process implementation; it can degrade safely to the simple demo while still offering credible differentiation when gates pass.

A secondary clash concerns replay. Its supporters see deterministic replay as essential for testing and demo resilience; critics warn that it can conceal weak live reliability. The supporters prevail only if replay is explicitly labeled and paired with measured live results on the target machine.

## Blind spots

The council did not define concrete pass/fail thresholds. Before building, the team still needs an acceptance contract covering ID switches or fragmentation, event precision/recall, p95 latency, repeatability, and maximum processing time on target hardware. It also lacks confirmed licensed footage, labeled ground truth, hardware benchmarks, team skill information, and evidence about the judging rubric. Day 6 needs a clean-room run from fresh checkout, dependency/license review, privacy and upload-validation checks, regression execution, manifest verification, and a rehearsal of degraded and replay modes.

## Recommendation

Choose the stage-gated hybrid centered on one proof-carrying hero behavior, plus one or two simpler behaviors. Build it as a monolithic FastAPI/Python/SQLite pipeline with a thin Next.js evidence-review UI; cut the generalized Temporal Scene Graph, assistant, generated client, blur, broad taxonomy, and generalized state-machine framework. Admit targeted verification only after it measurably improves event quality without violating the latency budget.

## One thing to do first

Within 48 hours, run a licensed representative clip on the target hardware and record predeclared tracking, event-quality, latency, and end-to-end upload→event→evidence acceptance results.

## Chairman-Dissent verdict

Council confidence: high (5/5 high, 0/5 medium, 0/5 low)  
Dominant assumption: A single-process baseline can achieve acceptable tracking stability on representative licensed footage and target hardware by the end of Day 1, leaving enough time for one visible temporal differentiator.  
Breakers: Day-1 ID-switch/fragmentation exceeds the predeclared threshold; Day-2 upload→event→evidence flow is not reliable at target p95 latency.

## Where the council agrees

The council rejects adopting the full revised architecture within six days. Red Team identifies too many coupled failure modes—fragmented tracks, verifier lag, inconsistent calibration, and untuned thresholds—while First Principles and Defender reframe the problem as failure containment rather than architecture completion. Executor, Outsider, and Expansionist independently converge on a narrow, end-to-end “hero slice” with replayable evidence.

The irreducible product is consistent across the advice: secure ingestion, detection/tracking histories, a small number of events, deterministic risk or policy outputs, time-linked evidence, and reproducibility. It should be one process with append-only records and simple SQLite, not a service topology. General Temporal Scene Graph machinery, broad configurable rules, generated clients, assistant dependency, sophisticated calibration, blur, and behavior breadth are all conditional or cut.

There is also agreement that gates must be measurable, not rhetorical. Tracking fragmentation and ID switches, event precision/recall, end-to-end p95 latency, and repeat-run determinism need acceptance thresholds on target hardware and representative licensed footage. No new interfaces should be introduced after Day 2, and scope should freeze after Day 3.

## Where the council clashes

The main disagreement is between a stage-gated hero hybrid and a simple YOLO-plus-rules dashboard. The hybrid’s strongest case, made by Executor, Expansionist, and First Principles, is that histories, targeted verification, evidence traces, and manifests provide visible and defensible differentiation without requiring the full graph architecture. One behavior demonstrated across three meaningful variants may communicate temporal intelligence more credibly than five shallow behaviors.

Prosecutor’s objection deserves unusual weight: even this “small” hybrid remains a distributed integration problem in disguise. If tracking fails early, the gates correctly eliminate the differentiators—but the team is then left with a narrow, unimpressive baseline, while a broader simple dashboard might have produced a stronger demo. Replay can further undermine trust if it conceals poor live performance, and architectural rigor is not valuable if judges mainly reward visible capability.

The hybrid is still more persuasive, but only narrowly and conditionally. Its advantage exists only if the temporal evidence is visible in the demo and passes an early tracking gate. Otherwise, the Prosecutor’s simpler dashboard should become the explicit fallback, not a degraded remnant of the hybrid.

## Blind spots

The council still lacks a named target-hardware acceptance contract, representative licensed clips, ground-truth annotation ownership, and Day-6 audit criteria. It also has not specified privacy retention/deletion behavior, model and footage license documentation, or the exact claims the demo may safely make. The proposed priority scores are pseudo-precise until these constraints are known. Finally, recorded-track replay must be clearly labeled and paired with a live test; otherwise reproducibility could be mistaken for real-world robustness.

## Recommendation

Choose the stage-gated hybrid, but precommit to a clean pivot into a polished YOLO-plus-rules dashboard if the Day-1 tracking gate fails. Build only two behaviors and three representative scenarios, with evidence traces and selective verification behind removable interfaces. Do not build the generalized scene graph, assistant, generated client, or advanced calibration unless all Day-3 gates are green.

## One thing to do first

Before writing product code, assemble and annotate a small licensed representative test set, then define pass/fail thresholds for ID switches, fragmentation, event precision/recall, and p95 latency on the actual demo hardware.

## Dissent Preservation Pass

- DISSENT PRESERVED: Precommit to a polished YOLO-plus-rules dashboard if Day-1 tracking fails — prevents a gated hybrid from collapsing into an unimpressive baseline; from the Prosecutor’s integration-risk challenge.
- DISSENT PRESERVED: Treat stable Day-1 tracking as the dominant schedule assumption — makes the temporal differentiator explicitly contingent on early feasibility; from the dissent chairman’s assumption analysis.
- DISSENT PRESERVED: Pair any replay with a live test — avoids replay masking weak live reliability and damaging evaluator trust; from the Prosecutor’s credibility challenge.
- DISSENT PRESERVED: Define privacy retention/deletion, model and footage licensing, safe claims, and ground-truth ownership — converts broad compliance checks into concrete demo obligations; from the dissent chairman’s blind-spot synthesis.

NOTE: Recommendations differ: the dissent verdict supports the hybrid only narrowly and requires an explicit Day-1 fallback, while the consensus verdict adopts the hybrid more directly.

## Full verdict

The final verdict is the Chairman-Consensus verdict above with the Dissent Preservation Pass appended. The operational decision is to pursue a stage-gated hero hybrid, while precommitting to the dissent chairman’s clean YOLO-plus-rules fallback if the Day-1 tracking gate fails.
