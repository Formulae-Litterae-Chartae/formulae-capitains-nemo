from lxml import etree
import re

def str_from_xml_paragraph(paragraph: etree._Element) -> str:
    """
    Extracts the words from all child nodes of the paragraph and applies appropriate inline formatting.
    Mirrors the inline logic of r_pdf() but adds modularity.
    """
    paragraph_str = ''
    hist_note_num = 1  # Footnote counter

    for c in paragraph.xpath('child::node()'):
        c_class = None
        c_text = ''

        if isinstance(c, etree._Element):
            c_class = c.get('class')
            c_text = c.text.replace('<', '&lt;').replace('>', '&gt;') if c.text else ''
        if isinstance(c, etree._ElementUnicodeResult):
            paragraph_str += c.replace('<', '&lt;').replace('>', '&gt;')
        elif c_class and 'w' in c_class.split():
            opening_tag = ''
            closing_tag = ''
            if 'font-italic' in c_class or 'latin-word' in c_class:
                opening_tag += '<i>'
                closing_tag = '</i>' + closing_tag
            if c.get('lemma') and 'platzhalter' in c.get('lemma'):
                opening_tag += '<b>'
                closing_tag = '</b>' + closing_tag
            if 'line-through' in c_class:
                opening_tag += '<strike>'
                closing_tag = '</strike>' + closing_tag
            if 'superscript' in c_class:
                opening_tag += '<super>'
                closing_tag = '</super>' + closing_tag
            if 'subscript' in c_class:
                opening_tag += '<sub>'
                closing_tag = '</sub>' + closing_tag
            paragraph_str += opening_tag + c_text + closing_tag
        elif c.xpath('./span') and c.xpath('./span')[0].get('class') and 'w' in c.xpath('./span')[0].get('class').split():
            opening_tag = ''
            closing_tag = ''
            word_span = c.xpath('./span')[0]
            c_class = word_span.get('class')
            c_text = word_span.text or ''
            if 'font-italic' in c_class or 'latin-word' in c_class:
                opening_tag += '<i>'
                closing_tag = '</i>' + closing_tag
            if word_span.get('lemma') and 'platzhalter' in word_span.get('lemma'):
                opening_tag += '<b>'
                closing_tag = '</b>' + closing_tag
            if 'line-through' in c_class:
                opening_tag += '<strike>'
                closing_tag = '</strike>' + closing_tag
            if 'superscript' in c_class:
                opening_tag += '<super>'
                closing_tag = '</super>' + closing_tag
            if 'subscript' in c_class:
                opening_tag += '<sub>'
                closing_tag = '</sub>' + closing_tag
            paragraph_str += opening_tag + c_text + closing_tag
        elif c.xpath('./a[@type="a1"]') or c.xpath('./a[@type="n1"]'):
            note_num = c.xpath('./a[@class="note"]')[0].text
            paragraph_str += '<sup>{}</sup>'.format(note_num)
        elif c_class and c.xpath('self::span[contains(@class, "right-note-tooltip")]|./a[@class="note"]'):
            if c.xpath('self::span[contains(@class, "right-note-tooltip")]'):
                text_to_add = ''.join(c.xpath('./text()')).replace('<', '&lt;').replace('>', '&gt;')
                paragraph_str += text_to_add
            paragraph_str += '<sup>{}</sup>'.format(hist_note_num)
            hist_note_num += 1

    return re.sub(u'\u200c', '', paragraph_str)

