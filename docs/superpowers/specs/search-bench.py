import shutil, sys, time
from pathlib import Path
from autoform_cli.search import search_blueprint
BODY = "A weak observation $S : Y \\to \\mathrm{Prop}$ is **non-ambiguous** when for every\npair $y \\neq y'$ there is a sample on which $S$ separates them, that is\n$$\\exists x, S(x, y) \\wedge \\neg S(x, y').$$\nThis is the hypothesis under which the infimum loss number %d recovers the\nfully supervised risk, and it is used by every consistency result in this chapter.\n"
root = Path(sys.argv[1]); n = int(sys.argv[2])
if root.exists(): shutil.rmtree(root)
rm = root / "blueprint" / "roadmap"; rm.mkdir(parents=True)
(rm / "README.md").write_text("# Book\n")
for i in range(n):
    ch = rm / f"ch{i // 20:04d}"
    if not ch.exists():
        ch.mkdir(); (ch / "README.md").write_text(f"# Chapter {i // 20}\n")
    dep = f"- [prev](a{i-1:05d}.md)\n" if i % 20 else ""
    (ch / f"a{i:05d}.md").write_text(f"---\ndeclaration: theorem\n---\n# Result {i}\n\n{BODY % i}\n## Depends on\n\n{dep}")
for q in ["non-ambiguous", "zzzz", "result 17"]:
    best = min((lambda s: (search_blueprint(root, q), time.perf_counter() - s)[1])(time.perf_counter()) for _ in range(2))
    print(f"n={n} {q!r}: {best:.2f}s total={search_blueprint(root,q).total_matches}")
