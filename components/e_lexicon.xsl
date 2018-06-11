<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema" 
    xmlns:tei="http://www.tei-c.org/ns/1.0" 
    exclude-result-prefixes="xs tei"
    version="2.0">
    
    <xsl:output method="html" omit-xml-declaration="yes" indent="no"/>
    
    <xsl:strip-space elements="tei:p" />
    
    <xsl:template match="/">
        <xsl:variable name="theText">
            <xsl:call-template name="theText">
                <xsl:with-param name="text" select="tei:w"/>
            </xsl:call-template>
        </xsl:variable>
        <xsl:variable name="theNotes">
            <xsl:call-template name="extractNotes">
                <xsl:with-param name="text" select="tei:note"/>
            </xsl:call-template>
        </xsl:variable>
        <xsl:value-of select="$theText"/>
        <xsl:text>&#13;</xsl:text>
        <xsl:value-of select="$theNotes"/>
    </xsl:template>
    
    <xsl:template name="theText">
        <xsl:param name="text"/>
        <!-- I may need to add the ability to strip space from <p> tags if this produces too much space once we start exporting form CTE -->
        <xsl:if test="not(preceding-sibling::node()[1][self::text()])">
            <xsl:text> </xsl:text>
        </xsl:if>
        <xsl:choose>
            <xsl:when test="parent::tei:seg[@type='italic']"><span class="w font-italic"><xsl:value-of select="."/></span></xsl:when>
            <xsl:otherwise><span class="w"><xsl:value-of select="."/></span></xsl:otherwise>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template name="extractNotes">
        <xsl:param name="text"/>
        <xsl:for-each select="$text">
            <xsl:number value="count(preceding::tei:note) + 1" format="1"/>: <xsl:value-of select="concat(replace(string-join(.//text(), ' '), '\s+', ' '), '; ')"/>
        </xsl:for-each>
    </xsl:template>
    
</xsl:stylesheet>