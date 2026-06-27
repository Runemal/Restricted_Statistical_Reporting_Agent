from etl_tool.telegram import render_telegram_html


def test_render_telegram_html_bolds_hash_headings_and_escapes_text():
    html = render_telegram_html("#Заголовок\nОбычный <текст> & данные")

    assert html == "<b>Заголовок</b>\nОбычный &lt;текст&gt; &amp; данные"
