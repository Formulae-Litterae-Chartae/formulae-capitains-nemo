<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:t="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs t"
    version="1.0">
    
    <xsl:output method="html" omit-xml-declaration="yes" indent="no"/>
    
    <xsl:template match="/">
        <xsl:text>{</xsl:text>
        <xsl:text>"citation": "</xsl:text><xsl:value-of select="/t:TEI/t:teiHeader/t:fileDesc/t:titleStmt/t:title"/><xsl:text>",</xsl:text>
        <xsl:text>"header": "</xsl:text><xsl:value-of select="/t:TEI/t:teiHeader/t:fileDesc/t:titleStmt/t:title"/><xsl:text>",</xsl:text>
        <xsl:text>"paragraphs": [</xsl:text>
        <xsl:for-each select="/t:TEI/t:text/t:body/t:div/t:div/t:p">
            <xsl:text>"</xsl:text>
            <xsl:for-each select="child::node()">
                <xsl:choose>
                    <xsl:when test="self::t:w">
                        <xsl:value-of select="./text()"/>
                    </xsl:when>
                    <xsl:when test="child::t:w">
                        <xsl:for-each select="child::node()">
                            <xsl:choose>
                                <xsl:when test="self::t:w">
                                    <xsl:call-template name="forWords"/>
                                </xsl:when>
                                <xsl:when test="self::text()">
                                    <xsl:value-of select="."/>
                                </xsl:when>
                            </xsl:choose>
                        </xsl:for-each>
                    </xsl:when>
                    <xsl:when test="child::*/child::t:w">
                        <xsl:for-each select="child::*/child::node()">
                            <xsl:choose>
                                <xsl:when test="self::t:w">
                                    <xsl:call-template name="forWords"/>
                                </xsl:when>
                                <xsl:when test="self::text()">
                                    <xsl:value-of select="."/>
                                </xsl:when>
                            </xsl:choose>
                        </xsl:for-each>
                    </xsl:when>
                    <xsl:when test="child::*/child::*/child::t:w">
                        <xsl:for-each select="child::*/child::*/child::node()">
                            <xsl:choose>
                                <xsl:when test="self::t:w">
                                    <xsl:call-template name="forWords"/>
                                </xsl:when>
                                <xsl:when test="self::text()">
                                    <xsl:value-of select="."/>
                                </xsl:when>
                            </xsl:choose>
                        </xsl:for-each>
                    </xsl:when>
                    <xsl:when test="self::text()">
                        <xsl:value-of select="."/>
                    </xsl:when>
                    <xsl:when test="self::t:note">
                        <sup>
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
                            <xsl:if test="following-sibling::node()[1][self::t:note]"><xsl:text>/</xsl:text></xsl:if>
                        </sup>
                    </xsl:when>
                </xsl:choose>
            </xsl:for-each>
            <xsl:text>"</xsl:text><xsl:if test="not(position() = last())"><xsl:text>, </xsl:text></xsl:if>
        </xsl:for-each>
        <xsl:text>],</xsl:text>
        <xsl:text>"app": [</xsl:text>
        <xsl:for-each select="//t:note[@type='a1']">
            <xsl:text>"</xsl:text>
                <sup>
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
                </sup>
                <xsl:text> </xsl:text>
                <xsl:apply-templates mode="noteSegs"/>
            <xsl:text>"</xsl:text><xsl:if test="not(position() = last())"><xsl:text>, </xsl:text></xsl:if>
        </xsl:for-each>
        <xsl:text>], </xsl:text>
        <xsl:text>"hist_notes": [</xsl:text>
        <xsl:for-each select="//t:note[@type='n1']">
            <xsl:text>"</xsl:text>
            <sup>
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
            </sup>
            <xsl:text> </xsl:text>
            <xsl:apply-templates mode="noteSegs"/>
            <xsl:text>"</xsl:text><xsl:if test="not(position() = last())"><xsl:text>, </xsl:text></xsl:if>
        </xsl:for-each>
        <xsl:text>]}</xsl:text>
               
        
    </xsl:template>
    
    <xsl:template match="t:w" name="forWords">
        <!-- I may need to add the ability to strip space from <p> tags if this produces too much space once we start exporting form CTE -->
        <!--<xsl:if test="not(preceding-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if> -->
        <xsl:param name="tags">
            <xsl:if test="contains(parent::t:seg/@rend, 'italic') or contains(parent::t:seg/@type, 'italic') or contains(parent::t:seg/@type, 'latin-word')">
                <xsl:text>i </xsl:text>
            </xsl:if>
            <xsl:if test="contains(parent::t:seg/@type, 'platzhalter')"><xsl:text>b </xsl:text></xsl:if>
            <xsl:if test="contains(parent::t:seg/@type, 'line-through')"><xsl:text>strike </xsl:text></xsl:if>
            <xsl:if test="contains(parent::t:seg/@type, 'superscript')"><xsl:text>super </xsl:text></xsl:if>
            <xsl:if test="contains(parent::t:seg/@type, 'subscript')"><xsl:text>sub </xsl:text></xsl:if>
        </xsl:param>
        <xsl:choose>
            <xsl:when test="not($tags = '')">
                <xsl:call-template name="buildTags">
                <xsl:with-param name="theText"><xsl:value-of select="."/></xsl:with-param>
                <xsl:with-param name="theTags" select="$tags"></xsl:with-param>
            </xsl:call-template>
            </xsl:when>
            <xsl:otherwise><xsl:value-of select="."/></xsl:otherwise>
        </xsl:choose>
        <!--<xsl:element name="span">
            <xsl:attribute name="style">
                <xsl:if test="contains(parent::t:seg/@rend, 'italic')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'italic')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'platzhalter')"><xsl:text>font-weight: bold;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'latin-word')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'small-caps')"><xsl:text>font-variant: small-caps;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'line-through')"><xsl:text>text-decoration: line-through;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'superscript')"><xsl:text>vertical-align: super;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'subscript')"><xsl:text>vertical-align: sub;</xsl:text></xsl:if>
                <xsl:if test="contains(parent::t:seg/@type, 'smaller-text')"><xsl:text>font-size: smaller;</xsl:text></xsl:if>
                <xsl:if test="parent::t:label">text-transform: uppercase;</xsl:if>
            </xsl:attribute>
            <!-\-<xsl:apply-templates/>-\->
            <xsl:value-of select="."/>
        </xsl:element>-->
        <!--<xsl:if test="not(following-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if>-->
        <!--<xsl:value-of select="following-sibling::node()[self::text()][1]"/>-->
    </xsl:template>
    
    <xsl:template match="t:seg" mode="noteSegs">
        <xsl:choose>
            <xsl:when test="./@type='book_title'">
                <xsl:element name="bibl">
                    <xsl:apply-templates/>
                </xsl:element>
            </xsl:when>
            <xsl:otherwise>
                <xsl:variable name="tags">
                    <xsl:if test="contains(./@rend, 'italic') or contains(./@type, 'italic') or contains(./@type, 'latin-word')">
                        <xsl:text>i </xsl:text>
                    </xsl:if>
                    <xsl:if test="contains(./@type, 'platzhalter')"><xsl:text>b </xsl:text></xsl:if>
                    <xsl:if test="contains(./@type, 'line-through')"><xsl:text>strike </xsl:text></xsl:if>
                    <xsl:if test="contains(./@type, 'superscript')"><xsl:text>super </xsl:text></xsl:if>
                    <xsl:if test="contains(./@type, 'subscript')"><xsl:text>sub </xsl:text></xsl:if>
                </xsl:variable>
                <xsl:choose>
                    <xsl:when test="not($tags = '')">
                        <xsl:call-template name="buildTags">
                            <xsl:with-param name="theText"><xsl:value-of select="."/></xsl:with-param>
                            <xsl:with-param name="theTags" select="$tags"></xsl:with-param>
                        </xsl:call-template>
                    </xsl:when>
                    <xsl:otherwise><xsl:value-of select="."/><xsl:text> </xsl:text></xsl:otherwise>
                </xsl:choose>
                <!--<xsl:element name="span">
                    <xsl:attribute name="style">
                        <xsl:if test="contains(./@rend, 'italic')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'italic')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'platzhalter')"><xsl:text>font-weight: bold;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'latin-word')"><xsl:text>font-style: italic;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'small-caps')"><xsl:text>font-variant: small-caps;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'line-through')"><xsl:text>text-decoration: line-through;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'superscript')"><xsl:text>vertical-align: super;</xsl:text></xsl:if>
                        <xsl:if test="contains(./@type, 'smaller-text') and not(contains(./@type, 'subscript'))"><xsl:text>font-size: smaller;</xsl:text></xsl:if>
                        <xsl:if test="./@rend='italic'">font-style: italic;</xsl:if></xsl:attribute>
                    <xsl:choose>
                        <xsl:when test="contains(./@type, 'subscript') and contains(./@type, 'smaller-text')">
                            <sub><xsl:apply-templates/></sub>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:apply-templates/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:element>-->
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template name="buildTags">
        <xsl:param name="theTags"/>
        <xsl:param name="theText"/>
        <xsl:choose>
            <xsl:when test="not($theTags = '')">
                <xsl:call-template name="buildTags">
                    <xsl:with-param name="theText"><xsl:element name="{substring-before($theTags, ' ')}"><xsl:copy-of select="$theText"/></xsl:element></xsl:with-param>
                    <xsl:with-param name="theTags" select="substring-after($theTags, ' ')"></xsl:with-param>
                </xsl:call-template>
            </xsl:when>
            <xsl:otherwise><xsl:copy-of select="$theText"/></xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
</xsl:stylesheet>