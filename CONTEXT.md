# Chess Engine Arena

A CLI tool for running UCI chess engine matches and analyzing the resulting games for blunders.

## Language

**Engine**:
A UCI-compliant chess program identified by its directory name under `engines/`, capable of playing moves when given a position and time control.
_Avoid_: Bot, AI, player

**Game**:
A single chess contest between two engines, from the starting position (or book line) to a terminal result — checkmate, stalemate, draw by rule, resignation, or forfeit.
_Avoid_: Match, battle, round

**Series**:
A configured set of games between the same two engines under the same time control, producing a PGN file and optionally an analysis report.
_Avoid_: Tournament, match, session

**Time Control**:
The clock constraints for a game, expressed as a base time plus an increment added after each move (e.g. 3 minutes + 2 seconds). Used to configure both engines identically.
_Avoid_: Clock, timer, pace

**Opening Book**:
A bundled Polyglot-format file of opening lines, provided to both engines to ensure varied starting positions across games in a series.
_Avoid_: Book, repertoire, openings file

**Blunder**:
A move by the tracked engine that causes a large negative evaluation swing from a near-equal position. Detected during analysis. Parameters: maximum pre-move equality margin (`equal_range`) and minimum evaluation drop (`blunder_delta`), both in engine centipawns.
_Avoid_: Mistake, error, inaccuracy

**Subject Engine**:
The engine under test in a series — its blunders are tracked during analysis. Typically an experimental engine being evaluated.
_Avoid_: Tested engine, target engine, tracked engine

**Analysis Engine**:
A strong engine used post-match to evaluate positions in completed games and detect blunders made by the subject engine.
_Avoid_: Reviewer, analyzer

**Analysis**:
Post-match review of a completed game by the analysis engine, evaluating each position to detect blunders made by the subject engine and annotating the PGN with evaluations.
_Avoid_: Review, inspection, post-mortem
