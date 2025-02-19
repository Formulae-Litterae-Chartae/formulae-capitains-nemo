from lxml import etree
from xml.etree.ElementTree import Element

def _str_from_xml_element(p:str, xml_element: Element) -> str:
    """
    Extract all words from lxml-Element
    """
    c_class = None
    c_text = ''
    if isinstance(xml_element, etree._Element):
        c_class = xml_element.get('class')
        c_text = xml_element.text.replace('<', '&lt;').replace('>', '&gt;') if xml_element.text else ''
    
    if isinstance(xml_element, etree._ElementUnicodeResult):
        p += xml_element.replace('<', '&lt;').replace('>', '&gt;')
    elif c_class and 'w' in c_class.split():
        opening_tag = ''
        closing_tag = ''
        if 'font-italic' in c_class or 'latin-word' in c_class:
            opening_tag += '<i>'
            closing_tag = '</i>' + closing_tag
        if xml_element.get('lemma') and 'platzhalter' in xml_element.get('lemma'):
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
        p += opening_tag + c_text + closing_tag
    elif xml_element.xpath('./span') and xml_element.xpath('./span')[0].get('class') and 'w' in xml_element.xpath('./span')[0].get('class').split():
        opening_tag = ''
        closing_tag = ''
        word_span = xml_element.xpath('./span')[0]
        c_class = word_span.get('class')
        c_text = word_span.text
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
        p += opening_tag + c_text + closing_tag
    elif xml_element.xpath('./a[@type="a1"]') or xml_element.xpath('./a[@type="n1"]'):
        note_num = xml_element.xpath('./a[@class="note"]')[0].text
        p += '<sup>{}</sup>'.format(note_num)
    elif c_class and xml_element.xpath('self::span[contains(@class, "right-note-tooltip")]|./a[@class="note"]'):
        if xml_element.xpath('self::span[contains(@class, "right-note-tooltip")]'):
            text_to_add = ''.join(xml_element.xpath('./text()')).replace('<', '&lt;').replace('>', '&gt;')
            p += text_to_add
        p += '<sup>{}</sup>'.format(hist_note_num)
        hist_note_num += 1
    return p

def str_from_xml_paragraph(paragraph: Element) -> str:
    """
    Extract the words from all child and grandchild nodes of the paragraph.
    :param paragraph: 
    :return paragraph_str: String representation of all words in the paragraph.
    """
    paragraph_str = ''
    for child_node in paragraph.xpath('child::node()'):
        if isinstance(child_node, etree._ElementUnicodeResult):
            paragraph_str = _str_from_xml_element(paragraph_str, child_node)
        # I think this lines has a major impact on issue #1066
        else:
            for grandchild_node in child_node.xpath('child::node()'):
                paragraph_str = _str_from_xml_element(paragraph_str, grandchild_node)
    return paragraph_str

