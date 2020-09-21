<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs"
    version="1.0">
    
    <xsl:output omit-xml-declaration="yes" indent="yes"/>
    
    <xsl:template match="/">
        <xsl:variable name="text-urn" select="//a[@class='note'][1]/@text-urn"/>
        <xsl:choose>
            <xsl:when test="count(//a[@class='note' and @type='a1']) > 0 or count(//a[@class='note' and @type='n1']) > 0">
                <xsl:if test="count(//a[@class='note' and @type='a1']) > 0">
                    <xsl:element name="div">
                        <xsl:attribute name="class">card bg-hhgray px-0 text-white</xsl:attribute>
                        <xsl:attribute name="style">font-size: small;</xsl:attribute>
                        <xsl:element name="span">
                            <xsl:attribute name="class">apparatus-title text-white align-middle</xsl:attribute>
                            <xsl:element name="button">
                                <xsl:attribute name="id"><xsl:value-of select="$text-urn"/>-a1-hide-button</xsl:attribute>
                                <xsl:attribute name="class">btn btn-dark float-right btn-sm text-white m-0 p-0</xsl:attribute>
                                <xsl:attribute name="onclick">hideNotes('<xsl:value-of select="$text-urn"/> a1')</xsl:attribute>
                                <xsl:attribute name="title"></xsl:attribute>
                                <xsl:text>⊗</xsl:text>
                            </xsl:element>
                            <xsl:element name="button">
                                <xsl:attribute name="id"><xsl:value-of select="$text-urn"/>-a1-show-button</xsl:attribute>
                                <xsl:attribute name="class">btn btn-dark float-right btn-sm text-white m-0 p-0 hidden-button</xsl:attribute>
                                <xsl:attribute name="onclick">showNotes('<xsl:value-of select="$text-urn"/> a1')</xsl:attribute>
                                <xsl:attribute name="title"></xsl:attribute>
                                <xsl:text>⊕</xsl:text>
                            </xsl:element>
                        </xsl:element>
                    </xsl:element>
                    <xsl:for-each select="//a[@class='note' and @type='a1']">
                        <xsl:call-template name="build_note"/>
                    </xsl:for-each>
                </xsl:if>
                <xsl:if test="count(//a[@class='note' and @type='n1']) > 0">
                    <xsl:element name="div">
                        <xsl:attribute name="class">card bg-hhgray px-0</xsl:attribute>
                        <xsl:attribute name="style">font-size: small;</xsl:attribute>
                        <xsl:element name="span">
                            <xsl:attribute name="class">commentary-title text-white</xsl:attribute>
                            <xsl:element name="button">
                                <xsl:attribute name="id"><xsl:value-of select="$text-urn"/>-n1-hide-button</xsl:attribute>
                                <xsl:attribute name="class">btn btn-dark float-right btn-sm text-white m-0 p-0</xsl:attribute>
                                <xsl:attribute name="onclick">hideNotes('<xsl:value-of select="$text-urn"/> n1')</xsl:attribute>
                                <xsl:attribute name="title"></xsl:attribute>
                                <xsl:text>⊗</xsl:text>
                            </xsl:element>
                            <xsl:element name="button">
                                <xsl:attribute name="id"><xsl:value-of select="$text-urn"/>-n1-show-button</xsl:attribute>
                                <xsl:attribute name="class">btn btn-dark float-right btn-sm text-white m-0 p-0 hidden-button</xsl:attribute>
                                <xsl:attribute name="onclick">showNotes('<xsl:value-of select="$text-urn"/> n1')</xsl:attribute>
                                <xsl:attribute name="title"></xsl:attribute>
                                <xsl:text>⊕</xsl:text>
                            </xsl:element>
                        </xsl:element>
                    </xsl:element>
                    <xsl:for-each select="//a[@class='note' and @type='n1']">
                        <xsl:call-template name="build_note"/>
                    </xsl:for-each>
                </xsl:if>
            </xsl:when>
            <xsl:when test="count(//a[@class='note']) > 0">
                <xsl:for-each select="//a[@class='note']">
                    <xsl:call-template name="build_note"/>
                </xsl:for-each>
            </xsl:when>
        </xsl:choose>
    </xsl:template>
    
    <xsl:template name="build_note" match="a">
        <xsl:param name="ident" select="translate(@href, '#', '')"/>
        <xsl:element name="div">
            <xsl:attribute name="class">collapse multi-collapse <xsl:value-of select="@text-urn"/><xsl:text> </xsl:text><xsl:value-of select="@type"/> show two-line fade-out</xsl:attribute>
            <!--<xsl:attribute name="data-toggle">collapse</xsl:attribute>-->
            <xsl:attribute name="aria-expanded">false</xsl:attribute>
            <!--<xsl:attribute name="role">button</xsl:attribute>-->
            <!--<xsl:attribute name="href"><xsl:value-of select="concat('#', $ident)"/></xsl:attribute>-->
            <xsl:attribute name="aria-controls"><xsl:value-of select="$ident"/></xsl:attribute>
            <xsl:attribute name="id"><xsl:value-of select="$ident"/></xsl:attribute>
            <xsl:attribute name="type"><xsl:value-of select="@type"/></xsl:attribute>
            <!--<xsl:attribute name="style">width: 25rem;</xsl:attribute>-->
            <xsl:element name="div">
                <xsl:attribute name="lang">de</xsl:attribute>
                <xsl:attribute name="class">card</xsl:attribute>
                <xsl:attribute name="style">font-size: small; color: black; text-decoration: none;</xsl:attribute>
                <xsl:element name="span">
                    <xsl:element name="button">
                        <xsl:attribute name="type">button</xsl:attribute>
                        <xsl:attribute name="class">close expand</xsl:attribute>
                        <!--<xsl:attribute name="data-target"><xsl:value-of select="concat('#', $ident)"/></xsl:attribute>
                        <xsl:attribute name="data-toggle">collapse</xsl:attribute>-->
                        <xsl:attribute name="toExpand"><xsl:value-of select="$ident"/></xsl:attribute>
                        <xsl:attribute name="aria-label">Expand</xsl:attribute>
                        <xsl:element name="span">
                            <xsl:attribute name="aria-hidden">true</xsl:attribute>
                            <xsl:text>&#8691;</xsl:text>
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
            <xsl:attribute name="data-content"><xsl:value-of select="$closeButton"/><xsl:value-of select="@n"/></xsl:attribute>
            <xsl:attribute name="tabindex">0</xsl:attribute>
            <xsl:attribute name="data-container">body</xsl:attribute>
            <xsl:attribute name="data-toggle">bibl-popover</xsl:attribute>
            <xsl:attribute name="id"><xsl:value-of select="generate-id()"/></xsl:attribute>
            <xsl:attribute name="href">#</xsl:attribute>
            <xsl:attribute name="class">internal-link</xsl:attribute>
            <xsl:apply-templates/>
        </xsl:element>
    </xsl:template>
    
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
        
</xsl:stylesheet>