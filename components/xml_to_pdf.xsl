<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xmlns:t="http://www.tei-c.org/ns/1.0"
    exclude-result-prefixes="xs t"
    version="1.0">
    
    <xsl:output method="html" omit-xml-declaration="yes" indent="yes"/>
    
    <xsl:template match="/">
        <xsl:element name="html">
            <xsl:element name="head"/>
            <xsl:element name="body">
                <xsl:element name="div">
                    <xsl:attribute name="id">header_content</xsl:attribute>
                    <xsl:value-of select="/t:TEI/t:teiHeader/t:fileDesc/t:titleStmt/t:title"/>
                </xsl:element>
                <h1><xsl:value-of select="/t:TEI/t:teiHeader/t:fileDesc/t:titleStmt/t:title"/></h1>
                <xsl:for-each select="/t:TEI/t:text/t:body/t:div/t:div/t:p">
                    <xsl:element name="p">
                        <xsl:for-each select="child::node()">
                            <xsl:choose>
                                <xsl:when test="self::t:w">
                                    <xsl:call-template name="forWords"/>
                                </xsl:when>
                                <xsl:when test=".//t:w">
                                    <xsl:call-template name="forWords"/>
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
                    </xsl:element>
                </xsl:for-each>
                <xsl:element name="hr"/>
                <xsl:for-each select="//t:note">
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
                    <xsl:element name="br"></xsl:element>
                </xsl:for-each>
               </xsl:element>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="t:w" name="forWords">
        <!-- I may need to add the ability to strip space from <p> tags if this produces too much space once we start exporting form CTE -->
        <!--<xsl:if test="not(preceding-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if> -->
        <xsl:element name="span">
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
            <xsl:apply-templates/>
        </xsl:element>
        <!--<xsl:if test="not(following-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if>-->
        <!--<xsl:value-of select="following-sibling::node()[self::text()][1]"/>-->
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
                </xsl:element>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
</xsl:stylesheet>