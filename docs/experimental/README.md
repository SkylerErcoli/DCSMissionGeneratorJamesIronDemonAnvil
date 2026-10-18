# Iron Anvil experimental gameplay

**Status: [the first experimental preview is published](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.3.0-experimental.1). Windows packaging/coexistence and automated mission checks passed. Real DCS flight testing remains outstanding.**

Implemented: Broken Relay and Supply Denial, required/optional functional goals, one finite staged response with delay/cancel consequences, shared debrief, distance presets, mission kneeboards, local briefings, named presets and replay import/export. Read the [work log](PROGRESS.md) for exact checks and remaining limits.

This development line starts from the existing application on the `experimental` branch. The [stable 1.2.0 download](https://github.com/SkylerErcoli/DCSMissionGeneratorJamesIronDemonAnvil/releases/tag/v1.2.0), `main`, and the stable update feed remain unchanged.

The goal is a good evening of co-op flying for a small group: easy setup, meaningful decisions, surprising events, and a clear ending. The roadmap below mixes the initial design and later proposals, informed by the [source research](RESEARCH.md). The completed features are listed above; mixed-aircraft packages, rescue, external frameworks and campaign persistence are still future work.

## Recommended direction: a co-op operation night

Generate a self-contained operation with several related objectives and optional complications. Players choose their priorities, see the consequences, and can bring everyone home with a satisfying result even when the sortie does not go perfectly.

For example:

> **Operation Broken Relay** — Your group must disable an enemy logistics complex. An optional communications site coordinates its response force. Destroying the relay delays the response; intercepting an ammunition convoy prevents a later ground reinforcement. You can complete the main strike and leave, or accept a harder bonus objective. Return to base for a shared debrief showing which objectives you achieved and what your choices changed.

The first implementation should work for the existing aircraft selection and two-to-four-player group. Mixed aircraft, helicopters, campaign saves, and external frameworks can follow once that first mission is enjoyable and reliable.

## What to add, in priority order

| Priority | Proposal | What makes it fun | Relative effort / uncertainty |
| --- | --- | --- | --- |
| 1 | **Functional objectives and partial success** | Disable the fuel installation or command function. Earn a useful result without searching for the final tiny object. Bonus targets remain optional. | Medium; objective selection and multiplayer completion need careful changes. |
| 2 | **Linked objectives with consequences** | Choose whether to knock out communications, intercept a supply convoy, or attack the main target immediately. Each action changes a later encounter. | Medium–large; requires a per-objective state model and clear briefing. |
| 3 | **A restrained enemy response system** | Enemy reserves move from briefed staging areas after detection or attack. Players can disrupt them, disengage, or finish before they arrive. | Medium–large; DCS routing, activation and detection need flight tests. |
| 4 | **Mission length, pressure and intelligence presets** | Choose a short sortie or a longer operation, relaxed or intense opposition, and exact or approximate target information. | Medium; flight-time estimates must account for aircraft and terrain. |
| 5 | **Reconnaissance, target search and confirmation** | Locate a convoy, distinguish candidate sites, call for a mark, then verify the result. Information becomes something players earn. | Medium–large; visual identification and aircraft sensor support vary. |
| 6 | **Mixed-role co-op packages** | One friend flies CAP, another SEAD, another attacks, and a helicopter crew inserts troops or rescues pilots. Every role contributes to the same objective. | Large; multiple client flights, payloads, briefings and completion rules. |
| 7 | **Rescue, troop insertion and logistics** | A downed pilot creates a rescue opportunity; delivering a team captures a cleared site or establishes a forward rearm point. | Large; extraction behavior, landing zones and FARP services need simulator validation. |
| 8 | **Connected air defenses** | Destroying a radar or command node opens an approach corridor. SEAD changes the mission for everyone. | Large; optional Skynet evaluation and supported SAM layouts. |
| 9 | **Three-to-five-sortie mini-campaigns** | Damage, supply losses and captured locations carry into the next mission without managing an entire theater. | Very large; trustworthy mission-result import and versioned saves. |
| 10 | **Optional game-master compatibility** | A friend can direct the enemy or add a surprise through Olympus while the rest fly. | Large; optional host installation and compatibility tests. |

Effort is relative to this codebase, not a delivery estimate. Every gameplay change must be tested in DCS; archive validation alone cannot establish that it plays well.

## Smaller additions worth doing alongside gameplay

- Named squadron presets and a shared scenario seed so a group can repeat a favorite setup.
- A kneeboard with objective photographs or diagrams, frequencies, laser codes, recovery base and alternate base. Use generated diagrams or properly licensed images.
- Short radio updates for objective changes, observed reinforcements and optional tasks. Text first; optional bundled audio later.
- A debrief that reports objectives achieved, aircraft recovered, bonus tasks and the seed needed to replay. Reward mission contribution and recovery, rather than making kills the only useful activity.
- A low-spec preset that limits active AI separately from decorative scenery. Validate performance with a real multiplayer host.
- Terrain-aware clearance and placement checks where DCS can provide terrain information, plus curated templates tested at known sites. Offline coastline checks do not establish safe ground placement.
- Era and faction packs for coherent Cold War and WWII scenarios, including appropriate ground equipment and defenses. Germany's mission date alone does not make a WWII force set.

## Suggested first playable experiment

Build **Operation Broken Relay** on the existing facility mission type, with:

1. One required logistics objective and one optional communications objective.
2. A single limited response group activated after a briefed delay; destroying communications before dispatch delays it further.
3. Clear functional victory conditions with decorative scenery excluded.
4. An F10 operation-status menu and a final shared summary.
5. Seeded variation in objective order, positions and response timing.
6. The current CAP and air-defense switches respected throughout.

Keep this first experiment self-contained in the generated `.miz`. It should not require friends to install additional mods or change DCS scripting security settings. [The design and acceptance criteria](FIRST-EXPERIMENT.md) describe the proposed behavior precisely.

## Rules for the experimental line

- Keep commits on `experimental`; do not merge to `main`, retag 1.2.0, replace its assets, or change its release notes/update manifest as part of these experiments.
- Before distributing an experimental executable, give it a separate application identity, installation directory, preferences directory, mission-output directory and release/update channel. The experimental app now provides separate installation/data/output identities; experimental downloads are manual and never use the stable update feed.
- Publish experimental packages explicitly as prereleases; never point the stable updater at experimental builds.
- Make experimental behaviors opt-in and retain existing CAP/air-defense switches, protected tanker/AWACS support, friendly home-base supplies and multiplayer recovery behavior.
- Stage finite enemy reserves at sensible locations with travel time, warnings where appropriate, active-unit limits and deterministic random choices. Do not silently increase the difficulty whenever players succeed.
- Treat external frameworks as optional integration candidates. Pin versions, review licenses/attribution, and prove compatibility before bundling any code or assets.
- Require source/Lua regression checks and a real two-player DCS flight before calling a gameplay experiment ready for a group night.
