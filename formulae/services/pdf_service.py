from lxml import etree
import re

def str_from_xml_paragraph(paragraph: etree._Element) -> str:
    """
    Converts a TEI-based paragraph element into a styled HTML-like string for PDF rendering.

    This function processes each child node of a paragraph (<p>) element extracted from 
    transformed TEI-XML. It applies typographical formatting (e.g., italics, bold, superscript),
    encodes special characters, and inserts footnote markers inline. This logic mirrors a 
    previously working implementation from within the r_pdf() method, refactored for reusability.

    Recognized formatting logic includes:
    - <i> for elements with 'font-italic' or 'latin-word' classes
    - <b> for elements with a 'platzhalter' lemma
    - <strike>, <super>, <sub> for corresponding visual styles
    - <sup>[n]</sup> for footnotes and apparatus markers

    Args:
        paragraph (etree._Element): A paragraph (<p>) element from the transformed TEI XML.

    Returns:
        str: A string with inline HTML-style markup suitable for Paragraph() in ReportLab.
    """
    paragraph_str = ''
    hist_note_num = 1  # Counter for historical footnotes not typed as 'a1'

    for c in paragraph.xpath('child::node()'):
        c_class = None
        c_text = ''

        # Handle regular elements: extract class and text safely
        if isinstance(c, etree._Element):
            c_class = c.get('class')
            c_text = c.text.replace('<', '&lt;').replace('>', '&gt;') if c.text else ''
        
        # Handle raw text (Unicode text nodes)
        if isinstance(c, etree._ElementUnicodeResult):
            paragraph_str += c.replace('<', '&lt;').replace('>', '&gt;')

        # Handle elements with class 'w' (word-level markup)
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

        # Handle wrapped spans (e.g., nested word elements inside another tag)
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

        # Handle footnote markers (apparatus or note references)
        elif c.xpath('./a[@type="a1"]') or c.xpath('./a[@type="n1"]'):
            note_num = c.xpath('./a[@class="note"]')[0].text
            paragraph_str += '<sup>{}</sup>'.format(note_num)

        # Handle additional note types (e.g. historical tooltips)
        elif c_class and c.xpath('self::span[contains(@class, "right-note-tooltip")]|./a[@class="note"]'):
            if c.xpath('self::span[contains(@class, "right-note-tooltip")]'):
                text_to_add = ''.join(c.xpath('./text()')).replace('<', '&lt;').replace('>', '&gt;')
                paragraph_str += text_to_add
            paragraph_str += '<sup>{}</sup>'.format(hist_note_num)
            hist_note_num += 1

    # Strip zero-width non-joiners (used in TEI markup for segmentation, etc.)
    return re.sub(u'\u200c', '', paragraph_str)

from datetime import date
from io import BytesIO
import re
from copy import copy
from flask import Response, url_for
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Frame
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.pdfencrypt import StandardEncryption
from lxml import etree


def render_pdf_response(objectId, resolver, static_folder, check_project_team, transform,
                        get_passage, get_reffs, encryption_pw) -> Response:
    """Generates a PDF from TEI XML and returns a Flask Response with encryption if required."""
    metadata = resolver.getMetadata(objectId=objectId)
    is_formula = 'formulae_collection' in metadata.ancestors

    new_subref = get_reffs(objectId)[0][0]
    text = get_passage(objectId=objectId, subreference=new_subref)

    # Export and transform TEI to internal XML
    from MyCapytain.common.constants import Mimetypes
    transformed_str = transform(text, text.export(Mimetypes.PYTHON.ETREE), objectId)
    transformed_str = transformed_str.replace('<?xml version="1.0" encoding="UTF-8"?>', '')
    transformed_xml = etree.fromstring(transformed_str)

    # Document title and filename
    doc_title_raw = str(metadata.metadata.get_single('http://purl.org/dc/elements/1.1/title', lang=None))
    doc_title = re.sub(r'<span class="manuscript-number">(\w+)</span>', r'<sub>\1</sub>',
                       re.sub(r'<span class="verso-recto">([^<]+)</span>', r'<super>\1</super>', doc_title_raw))
    description = f'{doc_title} ({date.today().isoformat()})'
    filename = _slugify_filename(description)

    # Setup ReportLab document
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, title=description)

    style_sheet = getSampleStyleSheet()
    style_sheet['BodyText'].fontName = 'Liberation'
    style_sheet['BodyText'].fontSize = 12
    style_sheet['BodyText'].leading = 14.4

    note_style = copy(style_sheet['Normal'])
    note_style.name = 'Notes'
    note_style.fontSize = 10
    note_style.fontName = 'Liberation'

    cit_style = copy(style_sheet['Normal'])
    cit_style.name = 'DocCitation'
    cit_style.fontSize = 8
    cit_style.alignment = 1
    cit_style.leading = 9.6

    flowables = build_flowables(transformed_xml, doc_title, style_sheet, note_style)

    # 🔐 Encryption logic (using canvasmaker)
    encryption = None
    if check_project_team() is False and is_formula:
        encryption = StandardEncryption(
            userPassword='',
            ownerPassword=encryption_pw,
            canPrint=1,
            canModify=0,
            canCopy=0,
            canAnnotate=0
        )

    def canvasmaker(*args, **kwargs):
        return canvas.Canvas(*args, encrypt=encryption, **kwargs) if encryption else canvas.Canvas(*args, **kwargs)

    # Final PDF rendering
    doc.build(
        flowables,
        onFirstPage=lambda c, d: add_citation_info(c, d, metadata, is_formula, static_folder, objectId, cit_style),
        onLaterPages=lambda c, d: add_citation_info(c, d, metadata, is_formula, static_folder, objectId, cit_style),
        canvasmaker=canvasmaker
    )

    safe_filename = re.sub(r'\W+', '_', filename)
    return Response(buffer.getvalue(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment;filename={safe_filename}.pdf'})



def _slugify_filename(description: str) -> str:
    trans_table = str.maketrans({
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'ß': 'ss',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ẞ': 'Ss'
    })
    return ''.join(c.translate(trans_table) for c in description)


def build_flowables(transformed_xml: etree._Element, doc_title: str, styles, note_style) -> list:
    flowables = [Paragraph(doc_title, styles['Heading1'])]
    hist_note_num = 1

    for p in transformed_xml.xpath('/div/div/p'):
        flowables.append(Paragraph(str_from_xml_paragraph(p), styles['BodyText']))

    if transformed_xml.xpath('/div/div/p/sup/a[@type="a1"]'):
        flowables += [Spacer(1, 5), HRFlowable(), Spacer(1, 5)]
        for app_note in transformed_xml.xpath('/div/div/p/sup/a[@type="a1"]'):
            n = '<sup>{}</sup>'.format(app_note.text)
            for c in app_note.xpath('./span[@hidden="true"]/child::node()'):
                n += _format_note_content(c)
            flowables.append(Paragraph(re.sub(u'\u200c', '', n), note_style))

    if transformed_xml.xpath('/div/div/p/sup/a[not(@type="a1")]|/div/div/p/span[contains(@class, "right-note-tooltip")]'):
        flowables += [Spacer(1, 5), HRFlowable(), Spacer(1, 5)]
        hist_note_num = 1
        for app_note in transformed_xml.xpath('/div/div/p/sup/a[not(@type="a1")]|/div/div/p/span[contains(@class, "right-note-tooltip")]'):
            n = '<sup>{}</sup>'.format(hist_note_num)
            hist_note_num += 1
            for c in app_note.xpath('./span[@hidden="true"]/child::node()'):
                n += _format_note_content(c)
            flowables.append(Paragraph(re.sub(u'\u200c', '', n), note_style))

    return flowables


def _format_note_content(c) -> str:
    if isinstance(c, etree._ElementUnicodeResult):
        return c
    c_class = c.get('class') if isinstance(c, etree._Element) else None
    c_text = c.text or '' if isinstance(c, etree._Element) else ''
    opening_tag = ''
    closing_tag = ''
    if c_class:
        if 'italic' in c_class or 'latin-word' in c_class:
            opening_tag += '<i>'
            closing_tag = '</i>' + closing_tag
        if 'line-through' in c_class:
            opening_tag += '<strike>'
            closing_tag = '</strike>' + closing_tag
        if 'superscript' in c_class:
            opening_tag += '<super>'
            closing_tag = '</super>' + closing_tag
        if 'subscript' in c_class:
            opening_tag += '<sub>'
            closing_tag = '</sub>' + closing_tag
    return opening_tag + c_text + closing_tag


def add_citation_info(canvas, doc, metadata, is_formula, static_folder, objectId, cit_style):
    cit_string = '<font color="grey">' + re.sub(r',?\s+\[URL:[^\]]+\]', '',
                  str(metadata.metadata.get_single('http://purl.org/dc/terms/bibliographicCitation'))) + '</font><br/>'
    cit_string += '<font color="grey">URL: https://werkstatt.formulae.uni-hamburg.de' + \
                  url_for("InstanceNemo.r_multipassage", objectIds=objectId, subreferences='1') + '</font><br/>'
    cit_string += '<font color="grey">Heruntergeladen: ' + date.today().isoformat() + '</font>'
    cit_string = re.sub(r'<span class="manuscript-number">(\d+)</span>', r'<sub>\1</sub>', cit_string)
    cit_string = re.sub(r'<span class="verso-recto">([^<]+)</span>', r'<super>\1</super>', cit_string)
    cit_string = re.sub(r'<span class="surname">([^<]+)</span>', r'<b>\1</b>', cit_string)

    flow = [Paragraph(cit_string, cit_style)]
    f = Frame(doc.leftMargin - 0.9 * inch, 0.01 * inch,
              doc.pagesize[0] - 0.2 * inch, 0.7 * inch, showBoundary=0)

    canvas.saveState()

    if is_formula:
        canvas.drawImage(static_folder + 'images/logo_white.png', inch, inch,
                         width=doc.pagesize[0] - doc.rightMargin,
                         height=doc.pagesize[1] - 1.5 * inch)
        canvas.drawImage(static_folder + 'images/uhh-logo-web.gif', doc.leftMargin,
                         doc.pagesize[1] - 0.9 * inch, width=1.111 * inch, height=0.5 * inch,
                         mask=[255, 256, 255, 256, 255, 256])
        canvas.drawImage(static_folder + 'images/logo_226x113_white_bg.png',
                         (doc.pagesize[0] / 2) - 0.5 * inch, doc.pagesize[1] - 0.9 * inch,
                         width=inch, height=0.5 * inch, mask=[255, 256, 255, 256, 255, 256])
        canvas.drawImage(static_folder + 'images/adwhh200x113.jpg',
                         doc.pagesize[0] - doc.rightMargin - 0.88 * inch, doc.pagesize[1] - 0.9 * inch,
                         width=0.882 * inch, height=0.5 * inch)

    f.addFromList(flow, canvas)
    canvas.setFont('Times-Roman', 8)
    canvas.drawCentredString(doc.pagesize[0] / 2, 0.75 * inch, '{}'.format(doc.page))
    canvas.restoreState()
