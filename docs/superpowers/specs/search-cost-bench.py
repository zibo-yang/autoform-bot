import sys, time, shutil, statistics
from pathlib import Path
from autoform_cli.graph import load_graph
from autoform_cli.runtime import build_runtime_graph
from autoform_cli.markdown import content, rendered_visible_text, frontmatter_end
from autoform_cli.audit import audit_graph

BODY = """A weak observation $S : Y \\to \\mathrm{{Prop}}$ is **non-ambiguous** when for every
pair $y \\neq y'$ there is a sample on which $S$ separates them, that is
$$\\exists x,\\; S(x, y) \\wedge \\neg S(x, y').$$
This is the hypothesis under which the infimum loss number {i} recovers the
fully supervised risk, and it is used by every consistency result in this chapter.
"""
def make(root, n):
    if root.exists(): shutil.rmtree(root)
    rm = root / "blueprint" / "roadmap"; rm.mkdir(parents=True)
    (rm / "README.md").write_text("# Book\n")
    per = 20
    for i in range(n):
        ch = rm / f"ch{i // per:04d}"
        if not ch.exists():
            ch.mkdir(); (ch / "README.md").write_text(f"# Chapter {i // per}\n")
        dep = f"- [prev](a{i-1:05d}.md)\n" if i % per else ""
        (ch / f"a{i:05d}.md").write_text(
            f"---\ndeclaration: theorem\n---\n# Result {i}\n\n{BODY.format(i=i)}\n## Depends on\n\n{dep}")
def t(f):
    s = time.perf_counter(); r = f(); return time.perf_counter() - s, r
for n in (100, 1000, 3000):
    root = Path(sys.argv[1]) / f"bp{n}"; make(root, n)
    bp = root / "blueprint"
    tl, g = t(lambda: load_graph(bp))
    tr, rt = t(lambda: build_runtime_graph(g, project_root=root))
    texts = [nd.path.read_text() for nd in g.nodes.values()]
    def stmts():
        out = []
        for x in texts:
            ls = x.splitlines(); ls = ls[frontmatter_end(ls):]
            body = "\n".join(l for l in ls if not l.startswith("# "))
            out.append(body.split("\n## ")[0])
        return out
    ss = stmts()
    tm, _ = t(lambda: [content(s) for s in ss])
    tv, vis = t(lambda: [rendered_visible_text(s) for s in ss])
    tsub, _ = t(lambda: [("non-ambiguous" in v.casefold()) for v in vis])
    ta, _ = t(lambda: audit_graph(g))
    print(f"n={n:5d} articles={len(g.nodes):5d} load_graph={tl:6.2f}s runtime={tr:6.2f}s mask={tm:6.3f}s render_visible={tv:6.2f}s ({tv/len(ss)*1000:.2f} ms/article) substring={tsub*1000:.1f}ms audit={ta:5.2f}s")
