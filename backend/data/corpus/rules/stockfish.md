Stockfish terms are standard metrics used to evaluate how accurately a player played compared to the computer's top recommendations.

Here is a simple breakdown of how to read and interpret these terms:

### 1. UCI Played & UCI Best

**UCI** stands for *Universal Chess Interface*, which is the language chess engines use to communicate moves. It writes moves using the starting square and the ending square (e.g., `e2e4` instead of standard algebraic notation like `e4`).

* **UCI Played:** This is the move that was *actually played* by the human (or bot) in the game, written in the engine's raw coordinate format.
* **UCI Best:** This is the move that Stockfish calculated to be the absolute *strongest* move in that exact position.

### 2. Eval Before & Eval After

"Eval" is short for evaluation. Stockfish evaluates a chess position in terms of "pawns."

* A **positive number** (e.g., +1.50) means White is winning by roughly 1.5 pawns.
* A **negative number** (e.g., -0.80) means Black is winning by roughly 0.8 pawns.
* **M#** (e.g., +M4) means forced checkmate in that many moves.

Here is how to read the before/after metrics:

* **Eval Before:** The score of the position *before* the player made their move.
* **Eval After:** The score of the position *after* the player made their move.

### 3. CPL (Centipawn Loss)

A "centipawn" is 1/100th of a pawn. **CPL** measures how much worse your move was compared to Stockfish's top choice (the "UCI Best").

* If the **UCI Played** matches the **UCI Best**, your CPL is usually **0** (perfect move).
* If you play a slightly inaccurate move, you might lose 20–40 centipawns (a minor mistake).
* If you blunder a full piece, your CPL might be 300 or higher (losing the equivalent of 3 pawns).

Essentially, **CPL = (Eval Before) - (Eval After)** from the perspective of the player whose turn it is. A lower CPL means you played a highly accurate game.

---

### Putting it all together (An Example)

Imagine you are playing White:

* **Eval Before:** +1.00 (You are ahead by 1 pawn).
* **UCI Best:** `g1f3` (Developing your knight).
* **UCI Played:** `h2h4` (You push your rook pawn instead).
* **Eval After:** +0.50 (Your advantage dropped).
* **CPL:** 50 (You lost half a pawn's worth of advantage by not playing the best move).