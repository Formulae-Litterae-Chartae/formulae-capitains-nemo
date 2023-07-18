<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0" xmlns:t="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="t">
    
    <!--<xsl:strip-space elements="t:p" />-->
        
    <!-- glyphs -->
    <xsl:template name="split-refs">
        <xsl:param name="pText"/>
        <xsl:if test="string-length($pText)">
            <xsl:if test="not($pText=.)">
                <xsl:text> </xsl:text>
            </xsl:if>
            <xsl:element name="a">
                <xsl:attribute name="href">
                    <xsl:value-of select="concat('http://cts.perseids.org/api/cts/?request=GetPassage', '&#38;', 'urn=', substring-before(concat($pText,','),','))"/>
                </xsl:attribute>
                <xsl:attribute name="target">_blank</xsl:attribute>
                <xsl:value-of select="substring-before(concat($pText,','),',')" />
            </xsl:element>
            <xsl:call-template name="split-refs">
                <xsl:with-param name="pText" select=
                    "substring-after($pText, ',')"/>
            </xsl:call-template>
        </xsl:if>
    </xsl:template>

    <xsl:template match="//t:div[@type = 'translation']">
    <div>
      
      <xsl:attribute name="class">
        <xsl:text>text translation lang_</xsl:text>
        <xsl:value-of select="@xml:lang"/>
      </xsl:attribute>
        <xsl:attribute name="lang"><xsl:value-of select="substring(./@xml:lang, 1, 2)"/></xsl:attribute>
      
      
      <xsl:apply-templates/>
    
    </div>
  </xsl:template>
    
    <xsl:template match="t:w" name="addWords">
        <!-- I may need to add the ability to strip space from <p> tags if this produces too much space once we start exporting form CTE -->
        <!--<xsl:if test="not(preceding-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if> -->     
        <xsl:param name="wTag"/>
        <xsl:choose>
            <xsl:when test="following-sibling::node()[1][self::t:note[@place='right']//*[starts-with(text(), '[fol')]] and not($wTag)"></xsl:when>
            <xsl:otherwise>
                <xsl:element name="span">
                    <xsl:attribute name="id"><xsl:value-of select="generate-id()"/></xsl:attribute>
                    <xsl:attribute name="class">w<xsl:if test="current()[@lemmaRef]"><xsl:text> lexicon</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@rend, 'italic')]"><xsl:text> font-italic</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'italic')]"><xsl:text> font-italic</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'platzhalter')]"><xsl:text> platzhalter</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'latin-word')]"><xsl:text> latin-word</xsl:text></xsl:if>
                        <xsl:if test="@type='latin-word'"><xsl:text> latin-word</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'small-caps')]"><xsl:text> small-caps</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'line-through')]"><xsl:text> line-through</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'superscript')]"><xsl:text> superscript</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:seg[contains(@type, 'subscript')]"><xsl:text> subscript</xsl:text></xsl:if>
                        <xsl:if test="current()[@function='from-other'] or ancestor::t:seg[contains(@type, 'smaller-text')]"><xsl:text> smaller-text</xsl:text></xsl:if>
                        <xsl:if test="ancestor::t:label"> formulae-label</xsl:if>
                        </xsl:attribute>
                    <xsl:if test="@lemma">
                        <xsl:attribute name="lemma"><xsl:value-of select="@lemma"/></xsl:attribute>
                    </xsl:if>
                    <xsl:if test="@n">
                        <xsl:attribute name="n"><xsl:value-of select="@n"/></xsl:attribute>
                    </xsl:if>
                    <xsl:if test="current()[@lemmaRef]">
                        <xsl:attribute name="data-lexicon"><xsl:value-of select="@lemmaRef"/></xsl:attribute>
                        <xsl:attribute name="tabindex">0</xsl:attribute>
                        <xsl:attribute name="role">button</xsl:attribute>
                        <xsl:attribute name="data-container"><xsl:value-of select="concat('#', generate-id())"/></xsl:attribute>
                        <xsl:attribute name="data-toggle">modal</xsl:attribute>
                        <xsl:attribute name="data-target">#lexicon-modal</xsl:attribute>
                        <xsl:attribute name="data-dismiss">modal</xsl:attribute>
                    </xsl:if>
                    <xsl:if test="ancestor::t:seg[contains(@type, 'latin-word')]">
                        <xsl:attribute name="lang"><xsl:text>la</xsl:text></xsl:attribute>
                    </xsl:if>
                    <xsl:if test="current()[@type]">
                        <xsl:choose>
                            <xsl:when test="@type='latin-word'">
                                <xsl:attribute name="lang">la</xsl:attribute>
                            </xsl:when>
                            <xsl:otherwise>
                                <xsl:attribute name="type"><xsl:value-of select="@type"/></xsl:attribute>
                            </xsl:otherwise>
                        </xsl:choose>
                    </xsl:if>
                    <xsl:if test="@synch"><xsl:attribute name="shared-word"><xsl:value-of select="@synch"/></xsl:attribute></xsl:if>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template match="t:seg[@type='note-begin-marker']">
        <xsl:element name="span">
            <xsl:attribute name="note-marker"><xsl:value-of select="@n"/></xsl:attribute>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:pc">
        <xsl:element name="span">
            <xsl:attribute name="class">
                <xsl:text>pc_</xsl:text>
                <xsl:value-of select="@unit|@type"/>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>

    <xsl:template match="//t:div[@type = 'commentary']">
    <div>
      
      <xsl:attribute name="class">
        <xsl:text>text commentary lang_</xsl:text>
        <xsl:value-of select="@xml:lang"/>
      </xsl:attribute>
      
      
      <xsl:apply-templates/>
    
    </div>
  </xsl:template>
    
    <xsl:template match="t:div[@type = 'edition']">
        <div>
            <xsl:attribute name="class">
                <xsl:text>text lang_</xsl:text>
                <xsl:value-of select="@xml:lang"/>
                <xsl:choose>
                    <xsl:when test="@subtype='transcription'"><xsl:text> transcription</xsl:text></xsl:when>
                    <xsl:otherwise> edition</xsl:otherwise>
                </xsl:choose>
            </xsl:attribute>
            <xsl:attribute name="data-lang"><xsl:value-of select="./@xml:lang"/></xsl:attribute>
            <xsl:attribute name="lang"><xsl:value-of select="substring(./@xml:lang, 1, 2)"/></xsl:attribute>
            <xsl:if test="@xml:lang = 'heb'">
                <xsl:attribute name="dir">
                    <xsl:text>rtl</xsl:text>
                </xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </div>
    </xsl:template>
    
    <xsl:template match="t:div[@type = 'textpart']">
        <xsl:element name="div">
            <xsl:attribute name="class">
                <xsl:value-of select="@subtype" />
            </xsl:attribute>
            <xsl:apply-templates select="@urn" />
            <xsl:if test="./@sameAs">
               <xsl:element name="p">
                   <xsl:element name="small">
                       <xsl:text>Sources </xsl:text>
                       <xsl:choose>
                           <xsl:when test="@cert = 'low'">
                               <xsl:text>(D'après)</xsl:text>
                           </xsl:when>
                       </xsl:choose>
                       <xsl:text> : </xsl:text>
                       <xsl:call-template name="split-refs">
                           <xsl:with-param name="pText" select="./@sameAs"/>
                       </xsl:call-template>
                   </xsl:element>
               </xsl:element>
            </xsl:if>
            <xsl:choose>
                <xsl:when test="child::t:l">
                    <ol><xsl:apply-templates /></ol>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:apply-templates/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:l">
        <xsl:element name="li">
            <xsl:apply-templates select="@urn" />
            <xsl:attribute name="value"><xsl:value-of select="@n"/></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:lg">
        <xsl:element name="ol">
            <xsl:apply-templates select="@urn" />
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:pb">
        <div class='pb'><xsl:value-of select="@n"/></div>
    </xsl:template>
    
    <xsl:template match="t:ab/text()">
        <xsl:value-of select="." />
    </xsl:template>
    
    
    <xsl:template match="t:p">
        <xsl:element name="p">
            <xsl:if test="@style='subparagraph'"><xsl:attribute name="class">indented-paragraph</xsl:attribute></xsl:if>
            <xsl:if test="@style='text-center'"><xsl:attribute name="class">text-center</xsl:attribute></xsl:if>
            <xsl:if test="@xml:id">
                <xsl:attribute name="id">
                    <xsl:value-of select="@xml:id"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:if test="@corresp">
                <xsl:element name="a">
                    <xsl:attribute name="href"><xsl:text>#</xsl:text></xsl:attribute>
                    <xsl:attribute name="onclick"><xsl:text>goToLinkedParagraph('</xsl:text><xsl:value-of select="@corresp"/><xsl:text>', '</xsl:text><xsl:value-of select="@xml:id"/><xsl:text>')</xsl:text></xsl:attribute>
                    <xsl:attribute name="class">paragraph-link</xsl:attribute>
                    <xsl:attribute name="link-to"><xsl:value-of select="@corresp"/></xsl:attribute>
                    <xsl:attribute name="hidden"></xsl:attribute>
                    <i class="fas fa-anchor"></i>
                </xsl:element>
            </xsl:if>
            <xsl:apply-templates select="@urn" />
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    
    <xsl:template match="t:lb" />
    
    
    <xsl:template match="t:ex">
        <span class="ex">
            <xsl:text>(</xsl:text><xsl:value-of select="." /><xsl:text>)</xsl:text>
        </span>
    </xsl:template>
    
    <xsl:template match="t:abbr">
        <span class="abbr"><xsl:apply-templates/></span>
    </xsl:template>  
    
    <xsl:template match="t:expan">
        <span class="expan"><xsl:apply-templates/></span>
    </xsl:template> 
    
    <xsl:template match="t:gap">
        <span class="gap">
            <xsl:choose>
                <xsl:when test="@quantity and @unit='character'">
                    <xsl:value-of select="string(@quantity)" />
                </xsl:when>
                <xsl:otherwise>
                    <xsl:text>---</xsl:text>
                </xsl:otherwise>
            </xsl:choose>
            
        </span>
    </xsl:template>
    
    <xsl:template match="t:head">
        <xsl:element name="div">
            <xsl:attribute name="class">
                <xsl:text>head</xsl:text>
                <xsl:if test="contains(@rend, 'italic')"><xsl:text> font-italic</xsl:text></xsl:if>
            </xsl:attribute>
            <xsl:apply-templates />
            <xsl:apply-templates select="@urn" />
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:title">
        <xsl:choose>
            <xsl:when test="@type='caption'">
                <span class="h4" id="forms-intro"><xsl:apply-templates/></span>
            </xsl:when>
            <xsl:otherwise>
                <span class="h4" id="doc-num"><xsl:apply-templates/></span>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template match="@urn">
        <xsl:attribute name="data-urn"><xsl:value-of select="."/>/></xsl:attribute>
    </xsl:template>
    
    <xsl:template match="t:sp">
        <section class="speak">
            <xsl:if test="./t:speaker">
                <em><xsl:value-of select="./t:speaker/text()" /></em>
            </xsl:if>
            <xsl:choose>
                <xsl:when test="./t:lg">
                    <xsl:apply-templates select="./t:lg" />
                </xsl:when>
                <xsl:when test="./t:p">
                    <xsl:apply-templates select="./t:p" />
                </xsl:when>
                <xsl:otherwise>
                    <ol>
                        <xsl:apply-templates select="./t:l"/>
                    </ol>
                </xsl:otherwise>
            </xsl:choose>
        </section>
    </xsl:template>
    
    <xsl:template match="t:supplied">
        <span>
            <xsl:attribute name="class">supplied supplied_<xsl:value-of select='@cert' /></xsl:attribute>
            <xsl:text>[</xsl:text>
            <xsl:apply-templates/><xsl:if test="@cert = 'low'"><xsl:text>?</xsl:text></xsl:if>
            <xsl:text>]</xsl:text>
        </span>
    </xsl:template>  
    
    <xsl:template match="t:note">
        <xsl:param name="note_num">
            <!-- I will need to change this to testing if there is an @n attribute. If so, use the value there. If not, find count(preceding::t:note[@type="a1"]) + 1 -->
            <xsl:choose>
                <xsl:when test="current()[@type='n1']">
                    <xsl:number value="count(preceding::t:note[@type='n1']) + 1" format="1"/>
                </xsl:when>
                <xsl:when test="current()[@type='a1']">
                    <xsl:number value="count(preceding::t:note[@type='a1']) + 1" format="a"/>
                </xsl:when>
                <xsl:otherwise>
                    <xsl:number value="count(preceding::t:note) + 1" format="1"/>
                </xsl:otherwise>
            </xsl:choose>
        </xsl:param>
        <xsl:choose>
            <xsl:when test="@place='right' and .//*[starts-with(normalize-space(text()), '[fol')]">
                <xsl:element name="span">
                    <xsl:attribute name="id"><xsl:value-of select="generate-id()"/></xsl:attribute>
                    <xsl:attribute name="data-toggle">tooltip</xsl:attribute>
                    <xsl:attribute name="data-html">true</xsl:attribute>
                    <xsl:attribute name="title"></xsl:attribute>
                    <xsl:attribute name="class">btn btn-link p-0 right-note-tooltip text-body</xsl:attribute>
                    <xsl:attribute name="tabindex">0</xsl:attribute>
                    <xsl:attribute name="data-container"><xsl:value-of select="concat('#', generate-id())"/></xsl:attribute>
                    <xsl:element name="span">
                        <xsl:attribute name="hidden">true</xsl:attribute>
                        <xsl:attribute name="class">tooltipTitle</xsl:attribute>
                        <xsl:apply-templates mode="noteSegs"></xsl:apply-templates>
                    </xsl:element>
                    <xsl:apply-templates select="preceding-sibling::node()[1]"><xsl:with-param name="wTag">true</xsl:with-param></xsl:apply-templates>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="sup">
                    <xsl:if test="@type='a1'">
                        <xsl:attribute name="data-noteStart"><xsl:value-of select="@xml:id"/></xsl:attribute>
                        <xsl:attribute name="data-noteEnd"><xsl:value-of select="@targetEnd"/></xsl:attribute>
                    </xsl:if>
                    <xsl:element name="a">
                        <xsl:attribute name="class">note</xsl:attribute>
                        <!--<xsl:attribute name="data-toggle">collapse</xsl:attribute>-->
                        <xsl:attribute name="href"><xsl:value-of select="concat('#', generate-id())"/></xsl:attribute>
                        <xsl:attribute name="role">button</xsl:attribute>
                        <xsl:attribute name="aria-expanded">false</xsl:attribute>
                        <xsl:attribute name="aria-controls"><xsl:value-of select="generate-id()"/></xsl:attribute>
                        <xsl:attribute name="text-urn"><xsl:value-of select="translate(/t:TEI/t:text/t:body/t:div[1]/@n, ':.', '--')"/></xsl:attribute>
                        <xsl:attribute name="type"><xsl:value-of select="@type"/></xsl:attribute>
                        <xsl:value-of select="$note_num"/>
                        <xsl:element name="span">
                            <xsl:attribute name="hidden">true</xsl:attribute>
                            <xsl:apply-templates mode="noteSegs"></xsl:apply-templates>
                        </xsl:element>
                    </xsl:element>
                    <xsl:if test="following-sibling::*[1][self::t:note]">
                        <xsl:text>/</xsl:text>
                    </xsl:if>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template match="node()[self::text()][following-sibling::node()[1][self::t:note[@place='right']]]">
        <xsl:param name="wTag"/>
        <xsl:if test="$wTag"><xsl:value-of select="."/></xsl:if>
    </xsl:template>
    
    <!-- I don't think there will be any more anchors in the next conversion, at least none without notes associated with them. So I think I can probably delete this template. -->
    <xsl:template match="t:anchor[ancestor-or-self::t:div[@xml:lang='lat']]">
        <xsl:param name="app_id" select="concat('#', translate(@xml:id, 'a', 'w'))"></xsl:param>
        <xsl:param name="note_num"><xsl:number value="count(preceding::t:anchor) + 1" format="a"/></xsl:param>
        <xsl:element name="sup">
            <xsl:element name="a">
                <xsl:attribute name="class">note</xsl:attribute>
                <xsl:attribute name="data-toggle">collapse</xsl:attribute>
                <xsl:attribute name="href"><xsl:value-of select="concat('#', generate-id())"/></xsl:attribute>
                <xsl:attribute name="role">button</xsl:attribute>
                <xsl:attribute name="aria-expanded">false</xsl:attribute>
                <xsl:attribute name="aria-controls"><xsl:value-of select="concat('multiCollapseExample', $note_num)"/></xsl:attribute>
                <xsl:value-of select="$note_num"/>
                <xsl:element name="span">
                    <xsl:attribute name="hidden">true</xsl:attribute>
                    <xsl:apply-templates mode="found" select="//t:app[@from=$app_id]"/>
                </xsl:element>
            </xsl:element>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:app" mode="found">
        <xsl:for-each select="t:rdg">
            <xsl:choose>
                <xsl:when test="@wit">
                    <xsl:choose>
                        <xsl:when test="@wit='#'">
                            <xsl:value-of select="."/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="translate(@wit, '#', '')"/>: <xsl:value-of select="."/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
                <xsl:when test="@source">
                    <xsl:choose>
                        <xsl:when test="@source='#'">
                            <xsl:value-of select="."/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="translate(@source, '#', '')"/>: <xsl:value-of select="."/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>
            </xsl:choose>
        </xsl:for-each>
    </xsl:template>
    
    <xsl:template match="t:app"/>
    
    <xsl:template match="t:ref">
        <a class="urn">
            <xsl:attribute name="href">
                <xsl:value-of select="@target"/>
            </xsl:attribute>
            <xsl:value-of select="." />
            [*]
        </a>
    </xsl:template>
    
    <xsl:template match="t:choice">
        <span class="choice">
            <xsl:apply-templates/>
        </span>
    </xsl:template>
    
    <xsl:template match="t:unclear">
        <span class="unclear"><xsl:value-of select="." /></span>
    </xsl:template>
    
    <xsl:template match="t:seg" mode="noteSegs">
        <xsl:choose>
            <xsl:when test="./@type='book_title'">
                <xsl:element name="bibl">
                    <xsl:attribute name="n"><xsl:value-of select="./@n"/></xsl:attribute>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:element name="span">
                    <xsl:attribute name="class"><xsl:value-of select="normalize-space(translate(./@type, ';', ' '))"/><xsl:if test="./@rend='italic'"> italic</xsl:if></xsl:attribute>
                    <xsl:if test="./@rend='italic' or contains(./@type, 'italic')">
                        <xsl:attribute name="lang">la</xsl:attribute>
                    </xsl:if>
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template match="t:bibl" mode="noteSegs">
        <xsl:element name="bibl">
            <xsl:attribute name="source"><xsl:value-of select="@source"/></xsl:attribute>
            <xsl:attribute name="n"><xsl:value-of select="@n"/></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <!--<xsl:template match="t:seg">
        <xsl:element name="span">
            <xsl:attribute name="class"><xsl:value-of select="normalize-space(translate(./@type, ';', ' '))"/><xsl:if test="./@rend='italic'"> italic</xsl:if></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>-->
    
    <xsl:template match="t:seg[@type='lex-title']">
        <strong lang="la"><xsl:apply-templates/></strong>
    </xsl:template>
    
    <xsl:template match="t:seg[@type='foreign-text']">
        <span class="foreign-text"><xsl:apply-templates/></span>
    </xsl:template>
    
    <xsl:template match="t:seg[@function]">
        <xsl:element name="span">
            <xsl:attribute name="function"><xsl:value-of select="@function"/></xsl:attribute>
            <xsl:attribute name="title"><xsl:value-of select="translate(@function, '-', ' ')"/></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:seg[@type='deperditum']">
        <span class="foreign-text h5"><xsl:apply-templates/></span>
    </xsl:template>
    
    <xsl:template match="t:seg[@xml:id]">
        <xsl:element name="span">
            <xsl:attribute name="id"><xsl:value-of select="@xml:id"/></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:list">
        <ul class="list-unstyled">
            <xsl:apply-templates/>
        </ul>
    </xsl:template>
    
    <xsl:template match="t:item">
        <li>
            <xsl:apply-templates/>
        </li>
    </xsl:template>
    
    <xsl:template match="t:locus">
        <xsl:element name="span">
            <xsl:attribute name="class">locus</xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:teiHeader"/>
    
    <xsl:template match="t:table">
        <xsl:element name="table">
            <xsl:attribute name="class">table table-borderless table-sm<xsl:if test="@type='two-source'"> two-source-table</xsl:if></xsl:attribute>
            <xsl:if test="@xml:id">
                <xsl:attribute name="id">
                    <xsl:value-of select="@xml:id"/>
                </xsl:attribute>
            </xsl:if>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:row">
        <xsl:element name="tr">
            <xsl:attribute name="class">
                <xsl:if test="@style='text-center'">text-center</xsl:if>
                <xsl:if test="@n='siglen-row'"> font-weight-bold</xsl:if>
                <xsl:if test="@n='small-text-row'"> small-text-row</xsl:if>
            </xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:cell">
        <xsl:element name="td">
            <xsl:if test="@cols"><xsl:attribute name="colspan"><xsl:value-of select="@cols"/></xsl:attribute></xsl:if>
            <xsl:call-template name="addWords"/>
        </xsl:element>
    </xsl:template>
    
</xsl:stylesheet>
