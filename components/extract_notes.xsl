<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs"
    version="1.0">
    
    <xsl:output omit-xml-declaration="yes" indent="yes"/>
    
    <xsl:template match="/">
        <xsl:for-each select="//a[@class='note']">
            <xsl:call-template name="build_note"/>
        </xsl:for-each>
    </xsl:template>
    
    <xsl:template name="build_note" match="a">
        <xsl:param name="ident" select="translate(@href, '#', '')"/>
        <xsl:element name="div">
            <xsl:attribute name="class">collapse multi-collapse <xsl:value-of select="@text-urn"/></xsl:attribute>
            <!--<xsl:attribute name="data-toggle">collapse</xsl:attribute>-->
            <xsl:attribute name="aria-expanded">false</xsl:attribute>
            <!--<xsl:attribute name="role">button</xsl:attribute>-->
            <!--<xsl:attribute name="href"><xsl:value-of select="concat('#', $ident)"/></xsl:attribute>-->
            <xsl:attribute name="aria-controls"><xsl:value-of select="$ident"/></xsl:attribute>
            <xsl:attribute name="id"><xsl:value-of select="$ident"/></xsl:attribute>
            <xsl:attribute name="type"><xsl:value-of select="@type"/></xsl:attribute>
            <!--<xsl:attribute name="style">width: 25rem;</xsl:attribute>-->
            <xsl:element name="div">
                <xsl:attribute name="class">card</xsl:attribute>
                <xsl:attribute name="style">font-size: small; color: black; text-decoration: none;</xsl:attribute>
                <xsl:element name="span">
                    <xsl:element name="button">
                        <xsl:attribute name="type">button</xsl:attribute>
                        <xsl:attribute name="class">close</xsl:attribute>
                        <!--<xsl:attribute name="data-target"><xsl:value-of select="concat('#', $ident)"/></xsl:attribute>
                        <xsl:attribute name="data-toggle">collapse</xsl:attribute>-->
                        <xsl:attribute name="onclick">closeNote('<xsl:value-of select="$ident"/>')</xsl:attribute>
                        <xsl:attribute name="aria-label">Close</xsl:attribute>
                        <xsl:element name="span">
                            <xsl:attribute name="aria-hidden">true</xsl:attribute>
                            <xsl:text>☒</xsl:text>
                        </xsl:element>
                    </xsl:element>
                    <xsl:element name="sup"><xsl:value-of select="text()"/></xsl:element><xsl:text> </xsl:text><xsl:apply-templates mode="noteContent" select="span"/>
                </xsl:element>
            </xsl:element>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="span" mode="noteContent">
        <xsl:apply-templates/>
    </xsl:template>
    
    <xsl:template match="bibl">
        <xsl:param name="closeButton">
            <xsl:text>&lt;button type="button" class="close" aria-label="Close" onclick="closePopup('</xsl:text><xsl:value-of select="generate-id()"/><xsl:text>')"&gt;☒&lt;/button&gt;</xsl:text>
        </xsl:param>
        <xsl:element name="a">
            <xsl:attribute name="data-content"><xsl:value-of select="@source"/><xsl:value-of select="$closeButton"/></xsl:attribute>
            <xsl:attribute name="tabindex">0</xsl:attribute>
            <xsl:attribute name="data-container">body</xsl:attribute>
            <xsl:attribute name="data-toggle">bibl-popover</xsl:attribute>
            <xsl:attribute name="id"><xsl:value-of select="generate-id()"/></xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
        
</xsl:stylesheet>