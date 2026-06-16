Status: needs-triage

# Engine hangs queen with no compensation

**Category:** bug

## Position

```
5qk1/1pr4p/p2p2p1/P2PP3/1P1Q2P1/6P1/6K1/4R3 b - - 2 34
```

## Observed behavior

The engine (`blunderchess`) plays **Qf1** in this position. The white king on g2 can simply capture the queen (Kxf1), losing the queen for no compensation or follow-up. This is a game-losing blunder.

## Expected behavior

The engine should evaluate Qf1 as losing the queen and avoid it. Any reasonable evaluation should see Kxf1 as a refutation (the queen is undefended on f1 and the king captures it directly).

## Impact

This single move throws an otherwise playable position into a completely lost game, undermining the engine's playing strength.
