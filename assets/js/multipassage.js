var lexModal = $('#lexicon-modal');
//var scrollControl = document.getElementById('scroll-text-separate');

$(document).ready(function(){
//     $('.apparatus-title').append(appHeading);
//     $('.commentary-title').append(comHeading);
//     $('[id$="a1-hide-button"]').attr('title', appCloseButton)
//     $('[id$="a1-show-button"]').attr('title', appOpenButton)
//     $('[id$="n1-hide-button"]').attr('title', comCloseButton)
//     $('[id$="n1-show-button"]').attr('title', comOpenButton)
    
    // These are the popovers for the notes in the right column of the normal text view.
    $('[data-toggle="bibl-popover"]').popover(
      {placement: 'left', 
          boundary: 'window',
          template: '<div class="popover bibl-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    })
    $('[data-toggle="charter-bibl-popover"]').popover(
      {placement: 'right', 
          boundary: 'window',
          template: '<div class="popover charter-bibl-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    })
    
    $('body').on('click', '.bibl-popover a.close', function() {
        $( this ).closest('.bibl-popover').popover('hide');
    })
    
    // These are the popups in the elexicon modal notes.
    // This is required to initialize popovers that are not part of the DOM when the document is loaded.
    // https://github.com/twbs/bootstrap/issues/4215
    $(document).popover(
      {selector: '.modal-popover',
          placement: 'top', 
          boundary: 'window',
          template: '<div class="popover elex-modal-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    })
    
    // Automatically set the max-height of the note-card for each text depending on the number of texts
    var noteCardsLeft = $('.noteCardLeft').length;
    var max = $(window).height() * .35;
    if (noteCardsLeft == 2 ) {
        max = $(window).height() * .17;
    } else if (noteCardsLeft > 2) {
        max = $(window).height() * .11;
    }
    $('.noteCardLeft .notecard-row').each(function() {
        var h = $(this).height();
        $(this).css('height', Math.min(max + 12, h + 12));
    });
    var noteCardsRight = $('.noteCardRight').length;
    var max = $(window).height() * .35;
    if (noteCardsRight == 2 ) {
        max = $(window).height() * .17;
    } else if (noteCardsRight > 2) {
        max = $(window).height() * .11;
    }
    $('.noteCardRight .notecard-row').each(function() {
        var h = $(this).height();
        $(this).css('height', Math.min(max + 12, h + 12));
    });
    
    // Show expand icon only if the whole note is not shown. Thanks to http://jsfiddle.net/kedem/D9NCP/
    $('.two-line').each(function(index, element) {
        var noteHeight = $( element ).height();
        var textHeight = $( element ).find('.card').height();
        if (textHeight < noteHeight) {
            $( element ).find('.expand').hide();
            $( element ).removeClass('fade-out');
        }
    })
    
    // Expands and contracts the note when the expand arrow is clicked
    $('.expand').click(function() {
        $('#' + $(this).attr('toexpand')).toggleClass('expanded fade-out');
        if ($('#' + $(this).attr('toexpand')).hasClass('fade-out')) {
            $(this).attr('title', expMess);
        } else {
            $(this).attr('title', conMess);
        }
    })

    $('.expand').each(function() {
        $(this).attr('title', expMess);
    })
    
    if ( screen.width > 767 ) {
        $('.note').click(function() {
            var linkTarget = $(this).attr('href');
            $( linkTarget ).on("animationend", function() {this.classList.remove('flash-yellow')})
            $( linkTarget ).addClass( 'flash-yellow' );
            if ($(linkTarget).hasClass('fade-out')) {
                $(linkTarget).toggleClass('expanded fade-out');
                $( '[toexpand=' + linkTarget.replace('#', '') + ']' ).attr('title', conMess);
            }
        })
    } else {
        $('.note').click( function() {
            var text = $( $(this).attr('href') ).children('div').children('span').clone();
            text.children('button').remove();
            text.find('a[data-container]').attr({'data-toggle': 'elex-modal-popover', 'class': 'modal-popover'});
            $('#note-modal div.modal-body').html(text.html());
            $('#note-modal').modal('show');
        })
    }
    
    // AJAX request to change reading format and then refresh the page
    $('.reading-format-setter').on('click', function(event) {
        event.preventDefault();
        e = this;
        var subdomain = '';
        if (window.location.host == 'tools.formulae.uni-hamburg.de') {
            subdomain = '/dev'
        }
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
            if (this.readyState == 4) {
                if (this.status == 200) {
                    location.reload();
                } else {
                    alert('Failed to change reading direction')
                }
            }
        };
        request.open('GET', subdomain + '/reading_format/' + e.getAttribute('value'), true);
        request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
        request.send()
    })
    
    $('span.w.lexicon').each(function() {
        $(this).attr({
            'title': lexElementTitle[0] + '<span class="latin-word">' + $( this ).attr('data-lexicon').replace('_', ' ') + '</span>' + lexElementTitle[1],
            'data-toggle': 'tooltip',
            'data-html': 'true'
        })
    })
    
    $('span.w.lexicon').on({
        click: function() {
            showLexEntry($( this ));
        },
        keydown: function(event) {
            if (event.key == "Enter" || event.key == " ") {
                showLexEntry($( this ));
            }
            $( this ).tooltip('hide');
        },
        mouseover: function() {
            $( this ).tooltip('show');
            showLemma($( this ));
        },
        mouseout: function() {
            $( this ).tooltip('hide');
            hideLemma($( this ));
        },
        focusin: function() {
            $( this ).tooltip('show');
            showLemma($( this ));
        },
        focusout: function() {
            $( this ).tooltip('hide');
            hideLemma($( this ));
        }
    });
    
    $('span.w[lemma]').on({
        mouseover: function() {
            showLemma($( this ));
        },
        mouseout: function() {
            hideLemma($( this ));
        },
        focusin: function() {
            showLemma($( this ));
        },
        focusout: function() {
            hideLemma($( this ));
        }
    })
    
    $('div.mirador-viewer-pane').each(function() {
        var minusHeight = $(this).prev().height();
        var maxHeight = $(window).height() * .65;
        console.log(minusHeight, maxHeight);
        $(this).css({
            'height': maxHeight - minusHeight
        })
    })
})

function makePopupNote(id) {
    var popup = document.getElementById(id);
    popup.classList.toggle("show");
}

function closePopup(id) {
    document.getElementById(id).click();
}

function closeNote(id) {
    var popup = document.getElementById(id);
    popup.classList.toggle("show");
    var elements = document.getElementById(id).querySelectorAll("[aria-describedby]");
    for (let element of elements) {
        element.click();
    }
}

function showLemma(x) {
    var lemma = x.attr("n");
    var lem_box = document.getElementById("lem_box");
//     lem_box.setAttribute("default-data", lem_box.innerHTML);
    lem_box.innerHTML = lemma;
}

function hideLemma() {
    var lem_box = document.getElementById("lem_box");
    lem_box.innerHTML = lem_box.getAttribute("default-data");
//     lem_box.removeAttribute("default-data");
}

function hideNotes(c) {
    var nodeclass = c + ' show';
    var matches = document.getElementsByClassName(nodeclass);
    while (matches.length > 0) {
        matches.item(0).setAttribute('aria-expanded', 'false');
        matches.item(0).classList.remove('show');
    }
    document.getElementById(c.replace(' ', '-') + '-hide-button').classList.add('hidden-button');
    document.getElementById(c.replace(' ', '-') + '-show-button').classList.remove('hidden-button');
    var urn = c.replace(/ [an]1/, '');
    var appHide = document.getElementById(urn + '-a1' + '-hide-button');
    var comHide = document.getElementById(urn + '-n1' + '-hide-button');
    var appShow = document.getElementById(urn + '-a1'  + '-show-button');
    var comShow = document.getElementById(urn + '-n1'  + '-show-button');
    // If we are hiding all notes for a text, then the buttons for the apparatus and commentary should also be hidden and revealed.
    if (c.search(/ [an]1/) == -1) {
        if (appHide != null) {
            appHide.classList.add('hidden-button');
        };
        if (comHide != null) {
            comHide.classList.add('hidden-button');
        };
        if (appShow != null) {
            appShow.classList.remove('hidden-button');
        };
        if (comShow != null) {
            comShow.classList.remove('hidden-button');
        };
    } else {
        if (appHide != null && Boolean(appHide.classList.contains('hidden-button')) == false) {
            var allHidden = false;
        } else if (comHide != null && Boolean(comHide.classList.contains('hidden-button')) == false) {
            var allHidden = false;
        } else {
            var allHidden = true;
        };
        if ( allHidden == true ) {
            document.getElementById(urn + '-show-button').classList.remove('hidden-button');
            document.getElementById(urn + '-hide-button').classList.add('hidden-button');
        }
    };
}

function showNotes(c) {
    var matches = document.getElementsByClassName(c);
    for (var i=0; i<matches.length; i++) {
        matches[i].classList.add('show');
        matches[i].setAttribute('aria-expanded', 'true');
    }
    document.getElementById(c.replace(' ', '-') + '-show-button').classList.add('hidden-button');
    document.getElementById(c.replace(' ', '-') + '-hide-button').classList.remove('hidden-button');
    // If we are opening all notes for a text, then the buttons for the apparatus and commentary should also be hidden and revealed.
    var urn = c.replace(/ [an]1/, '');
    var appHide = document.getElementById(urn + '-a1' + '-hide-button');
    var comHide = document.getElementById(urn + '-n1' + '-hide-button');
    var appShow = document.getElementById(urn + '-a1'  + '-show-button');
    var comShow = document.getElementById(urn + '-n1'  + '-show-button');
    if (c.search(/ [an]1/) == -1) {
        if (appHide != null) {
            appHide.classList.remove('hidden-button');
        };
        if (comHide != null) {
            comHide.classList.remove('hidden-button');
        };
        if (appShow != null) {
            appShow.classList.add('hidden-button');
        };
        if (comShow != null) {
            comShow.classList.add('hidden-button');
        };
    } else {
        if (appShow != null && Boolean(appShow.classList.contains('hidden-button')) == false) {
            var allShown = false;
        } else if (comShow != null && Boolean(comShow.classList.contains('hidden-button')) == false) {
            var allShown = false;
        } else {
            var allShown = true;
        };
        if ( allShown == true ) {
            document.getElementById(urn + '-show-button').classList.add('hidden-button');
            document.getElementById(urn + '-hide-button').classList.remove('hidden-button');
        }
    };
}

function showLexEntry(word) {
        var lemma = word.attr('data-lexicon');
        var request = new XMLHttpRequest();
        var message = lexModal.attr('message');
        var subdomain = '';
        if (window.location.host == 'tools.formulae.uni-hamburg.de') {
            subdomain = '/dev'
        }
        request.onreadystatechange = function() {
            if (this.readyState == 4) {
                if (this.status == 200) {
                    lexModal.html(this.responseText);
                    lexModal.modal('show');
                } else {
                    alert(message + lemma)
                }
            }
        };
        request.open('GET', subdomain + '/lexicon/urn:cts:formulae:elexicon.' + lemma + '.deu001', true);
        request.send()
    }
    
function closeLexEntry() {
    lexModal.modal('hide');
}
    
window.onclick = function(event) {
    if (event.target == lexModal) {
        lexModal.modal('hide');
    }
}

//function changeScrollMode(el) {
//    var imgChild = el.children[0];
//    if (el.getAttribute('title') == toScrollingTexts || el.getAttribute('title') == '') {
//        el.setAttribute('title', fromScrollingTexts);
//        imgChild.setAttribute('src', scrollTogetherSrc);
//    } else {
//        el.setAttribute('title', toScrollingTexts);
//        imgChild.setAttribute('src', scrollIndependentSrc);
//    };
//    var textSections = document.querySelectorAll('.text-section');
//    for (let section of textSections) {
//        section.classList.toggle('scrolling');
//    }
//}

function goToLinkedParagraph(h, t) {
    var el = document.getElementById(t);
    /*var imgChild = scrollControl.children[0];
    if (scrollControl && (scrollControl.getAttribute('title') == toScrollingTexts || scrollControl.getAttribute('title') == '')) {
        scrollControl.setAttribute('title', fromScrollingTexts);
        imgChild.setAttribute('src', scrollTogetherSrc);
        var textSections = document.querySelectorAll('.text-section');
        for (let section of textSections) {
            section.classList.toggle('scrolling');
        }
    }*/
    target = document.getElementById(h);
    el.scrollIntoView();
    el.onanimationend =  function() {this.classList.remove('flash-grey')};
    el.classList.add( 'flash-grey' );
    target.scrollIntoView();
    target.onanimationend =  function() {this.classList.remove('flash-grey')};
    target.classList.add( 'flash-grey' );
};
