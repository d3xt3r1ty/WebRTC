# Changelog

## 3.6.15
- Keep `initial_stream` visible until the main video has actually rendered a frame, avoiding a black gap caused by handing off on `loadeddata` alone.

## 3.6.11
- Predictive zoom slider now keeps the thumb at the commanded/virtual target while the blue fill tracks the reported physical zoom position.
- The virtual target display remains visible long enough for the physical zoom mechanism to catch up.
