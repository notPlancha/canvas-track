"""Unit tests for MoodleLinkRewriter."""

from canvas_track.moodle_rewriter import MoodleLinkRewriter


def test_moodle_link_rewriter() -> None:
    rewriter = MoodleLinkRewriter(
        site_id="lnu",
        course_id=73674,
        base_domain="moodle.example.edu",
        cmid_to_page_url={5155310: "page-syllabus"},
        cmid_to_file_id={5155322: 998877},
    )

    html = (
        '<p>Please check the <a href="https://moodle.example.edu/mod/page/view.php?id=5155310">'
        "Syllabus</a> "
        'and the <a href="https://moodle.example.edu/mod/resource/view.php?id=5155322">'
        "Schedule File</a>.</p>"
        '<p>Assignment link: <a href="/mod/assign/view.php?id=5155329">Assignment 1</a></p>'
        '<p>Course Forum: <a href="https://moodle.example.edu/mod/forum/view.php?id=5155315">Forum</a></p>'
        '<img src="https://moodle.example.edu/webservice/pluginfile.php/10782681/content/hero.png" />'
    )

    rewritten = rewriter.rewrite_html(html)

    # Verify Page rewrite
    assert "#/site/lnu/course/73674/pages/page-syllabus" in rewritten
    # Verify Resource rewrite
    assert "/api/vault/files/lnu/73674/998877" in rewritten
    # Verify Assignment rewrite
    assert "#/site/lnu/course/73674/assignments/5155329" in rewritten
    # Verify Forum rewrite
    assert "#/site/lnu/course/73674/discussions/5155315" in rewritten
    # Verify Pluginfile rewrite
    assert 'src="/api/vault/files/lnu/73674/10782681"' in rewritten
