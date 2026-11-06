from canvas_track.rewriter import CanvasLinkRewriter


def test_canvas_link_rewriter_file_links() -> None:
    rewriter = CanvasLinkRewriter(
        site_id="ltu",
        course_id=29010,
        base_domain="canvas.ltu.se",
    )

    # 1. Absolute Canvas course file URL with query parameters
    html = (
        '<a href="https://canvas.ltu.se/courses/29010/files/4999932'
        '?verifier=b7a55e92&amp;wrap=1">Presentation</a>'
    )
    rewritten = rewriter.rewrite_html(html)
    assert 'href="/api/vault/files/ltu/29010/4999932"' in rewritten

    # 2. Folder preview file URL
    html = (
        '<a href="https://canvas.ltu.se/courses/29010/files/folder/lecture_slides'
        '?preview=5153128">Slides</a>'
    )
    rewritten = rewriter.rewrite_html(html)
    assert 'href="/api/vault/files/ltu/29010/5153128"' in rewritten

    # 3. Canvas object reference file URL
    html = '<a href="$CANVAS_OBJECT_REFERENCE$/files/4999905">Ref</a>'
    rewritten = rewriter.rewrite_html(html)
    assert 'href="/api/vault/files/ltu/29010/4999905"' in rewritten

    # 4. Global file download URL
    html = '<a href="https://canvas.ltu.se/files/4999915/download?download_frd=1">Download</a>'
    rewritten = rewriter.rewrite_html(html)
    assert 'href="/api/vault/files/ltu/29010/4999915"' in rewritten

    # 5. Relative file download URL
    html = '<a href="/courses/29010/files/4999914/preview">Preview</a>'
    rewritten = rewriter.rewrite_html(html)
    assert 'href="/api/vault/files/ltu/29010/4999914"' in rewritten


def test_canvas_link_rewriter_navigation_links() -> None:
    rewriter = CanvasLinkRewriter(
        site_id="ltu",
        course_id=29010,
        base_domain="canvas.ltu.se",
    )

    # Page links
    html = '<a href="https://canvas.ltu.se/courses/29010/pages/welcome-page">Welcome</a>'
    assert 'href="#/site/ltu/course/29010/pages/welcome-page"' in rewriter.rewrite_html(html)

    # Assignment links
    html = '<a href="https://canvas.ltu.se/courses/29010/assignments/12345">Assignment 1</a>'
    assert 'href="#/site/ltu/course/29010/assignments/12345"' in rewriter.rewrite_html(html)

    # Discussion links
    html = '<a href="/courses/29010/discussion_topics/67890">Forum</a>'
    assert 'href="#/site/ltu/course/29010/discussions/67890"' in rewriter.rewrite_html(html)
