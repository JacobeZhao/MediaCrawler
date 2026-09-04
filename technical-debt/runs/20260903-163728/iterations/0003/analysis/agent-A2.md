# A2 Behavior And Risk

Runtime composition, persistence, attribution, public exports, migrations, and
security/release work remains blocked by dependencies, missing characterization,
consumer evidence, protected data, or product decisions.

A2 ranks image downloader characterization first, runtime-lock characterization
second, and a dependency-free verification driver third. The image candidate
would freeze normalization, input/limit behavior, cache reuse, timeout/headers,
extension selection, atomic replacement, cleanup, ordering, and failure
isolation without selecting resource/destination policy. The runtime-lock
candidate is also ready but has medium platform risk because its implementation
is user-owned. Both are new-test-only R1 batches with high confidence.

A2 recommends image downloader characterization only and defers all
behavior-changing resource work.
