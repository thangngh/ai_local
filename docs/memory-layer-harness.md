# Memory Layer Harness

This harness validates memory layer policy from M0 to M5 and applies high-hop interference checks up to hop 20.

## Layers

| Layer | Meaning | Fact Policy |
| --- | --- | --- |
| M0 | Session scratch | Never fact |
| M1 | Personal preference | Hint only |
| M2 | Project convention | Fact only with project evidence |
| M3 | Confirmed decision | Fact with confirmation |
| M4 | Workflow memory | Fact when fresh and successful |
| M5 | Safety policy | Binding policy when confirmed |

## Gate Levels

- `easy`: M0/M1 classification and direct retrieval policy, max hop 2
- `medium`: M2/M3 evidence and confirmation requirements, max hop 5
- `hard`: M4/M5 stale, conflict, and safety policy behavior, max hop 10
- `extreme`: all memory layers under deep interference up to hop 20

## High-Hop Interference

Hop 20 is the configured maximum for adversarial chains. A memory claim relayed through many sources must still preserve:

- original source reference
- evidence strength
- scope
- role
- confirmation status
- conflict status
- sensitivity risk

Deep-hop repetition does not increase authority. Repeated untrusted claims remain untrusted.

## Command

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-layers
```

Stop at a level:

```powershell
.\.venv\Scripts\python -m ai_local.cli memory-layers --max-level hard
```

