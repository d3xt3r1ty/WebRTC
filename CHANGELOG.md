# Changelog

## 3.6.16
- `initial_stream` now first reuses a matching kept-alive card's live browser `MediaStream`, avoiding a second WebRTC negotiation during dashboard-to-full-view navigation.
- If no reusable kept-alive stream exists, the existing initial-stream connection is still attempted in parallel and never delays the main stream.
- Main-stream handoff continues to wait for the first rendered main frame.

## 3.6.15
- Keep `initial_stream` visible until the main video has actually rendered a frame, avoiding a black gap caused by handing off on `loadeddata` alone.

## 3.6.11
- Predictive zoom slider now keeps the thumb at the commanded/virtual target while the blue fill tracks the reported physical zoom position.
- The virtual target display remains visible long enough for the physical zoom mechanism to catch up.
