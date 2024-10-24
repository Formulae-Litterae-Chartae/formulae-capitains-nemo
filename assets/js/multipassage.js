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
        var newHeight = Math.min(max + 12, h + 12);
        $(this).css('height', newHeight);
        $(this).attr('oldHeight', newHeight);
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
        var newHeight = Math.min(max + 12, h + 12);
        $(this).css('height', newHeight);
        $(this).attr('oldHeight', newHeight);
    });
    
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

    $('span.w').on({
        mouseover: function() {
            $( this ).tooltip('show');
            showLemma($( this ));
            $( this ).addClass('word-graph-focus');
        },
        mouseout: function() {
            $( this ).tooltip('hide');
            hideLemma($( this ));
            $( this ).removeClass('word-graph-focus');
        },
        focusin: function() {
            $( this ).tooltip('show');
            showLemma($( this ));
            $( this ).addClass('word-graph-focus');
        },
        focusout: function() {
            $( this ).tooltip('hide');
            hideLemma($( this ));
            $( this ).removeClass('word-graph-focus');
        },
//         dblclick: function() {
//             var wordGraphModal = $( '#word-graph-modal' );
//             var request = new XMLHttpRequest();
//             var subdomain = '';
//             if (window.location.host == 'tools.formulae.uni-hamburg.de') {
//                 subdomain = '/dev'
//             }
//             request.onreadystatechange = function() {
//                 if (this.readyState == 4) {
//                     if (this.status == 200) {
//                         wordGraphModal.html(this.responseText);
//                         wordGraphModal.modal('show');
//                     } else {
//                         alert(message)
//                     }
//                 }
//             };
//             request.open('GET', subdomain + '/collocations/' + $( this ).attr('inflected') + '/None', true);
//             request.send()
//         }
    })

    $(document).keypress(function(e){
        if (e.key ==  "Enter" ) {
            openWordGraphModal($( '.word-graph-focus' ).attr('inflected'), $( '.word-graph-focus' ).attr('lemma'), 'inflected')
        }
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
            lexModal.modal('show', $( this ));
        },
        keydown: function(event) {
            if (event.key == "Enter" || event.key == " ") {
                lexModal.modal('show', $( this ));
            }
            $( this ).tooltip('hide');
        }
    });
    
//     $('span.w[lemma]').on({
//         mouseover: function() {
//             showLemma($( this ));
//         },
//         mouseout: function() {
//             hideLemma($( this ));
//         },
//         focusin: function() {
//             showLemma($( this ));
//         },
//         focusout: function() {
//             hideLemma($( this ));
//         }
//     })
    
    $('div.mirador-viewer-pane').each(function() {
        var minusHeight = $(this).prev().height();
        var maxHeight = $(window).height() * .65;
        console.log(minusHeight, maxHeight);
        $(this).css({
            'height': maxHeight - minusHeight
        })
    })
    
    
    lexModal.on('show.bs.modal', function (event) {
        var button = $(event.relatedTarget) // Button that triggered the modal
        var lemma = button.data('lexicon'); // Extract info from data-* attributes
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
                    lexModal.modal('show', button);
                } else {
                    alert(message + lemma)
                }
            }
        };
        request.open('GET', subdomain + '/lexicon/urn:cts:formulae:elexicon.' + lemma + '.deu001', true);
        request.send()
    })

    $('sup[data-notestart]').on({
        mouseover: function() {
            var startNote = $( this ).attr('data-notestart');
            var noteEnd = $( this ).attr('data-noteEnd');
            if ($( 'span[note-marker="' + startNote + '"]' ).length > 0 ) {
                var endParent = $( noteEnd ).parent();
                var startParent = $( 'span[note-marker="' + startNote + '"]' ).parent();
                var startWord = $( 'span[note-marker="' + startNote + '"]' ).prevAll('.w').first();
                if (endParent.index() == startParent.index()) {
                    if ($( 'span[note-marker="' + startNote + '"]' ).index() < $( noteEnd ).index() ) {
                        $( this ).prevUntil(startWord, 'span').add(startWord).addBack().each(function() {
                            $( this ).addClass('bg-hhblue');
                        })
                    } else {
                        $( noteEnd ).addClass('bg-hhblue');
                    }
                } else {
                    $( this ).prevUntil(endParent.children().first( 'span' ), 'span').add(endParent.children().first( 'span' )).addBack().each(function() {
                        $( this ).addClass('bg-hhblue');
                    })
                    endParent.prevUntil( startParent ).each(function() {
                        $( this ).addClass('bg-hhblue');
                    })
                    startParent.children( 'span' ).last().prevUntil( startWord, 'span' ).add(startWord).add(startParent.children( 'span' ).last()).each(function() {
                        $( this ).addClass('bg-hhblue');
                    })
                }
            } else {
                $( noteEnd ).addClass('bg-hhblue');
            };
        },
        mouseout: function() {
            var startNote = $( this ).attr('data-notestart');
            var noteEnd = $( this ).attr('data-noteEnd');
            if ($( 'span[note-marker="' + startNote + '"]' ).length > 0 ) {
                var endParent = $( noteEnd ).parent();
                var startParent = $( 'span[note-marker="' + startNote + '"]' ).parent();
                var startWord = $( 'span[note-marker="' + startNote + '"]' ).prevAll('.w').first();
                if (endParent.index() == startParent.index()) {
                    if ($( 'span[note-marker="' + startNote + '"]' ).index() < $( noteEnd ).index() ) {
                        $( this ).prevUntil(startWord, 'span').add(startWord).addBack().each(function() {
                            $( this ).removeClass('bg-hhblue');
                        })
                    } else {
                        $( noteEnd ).removeClass('bg-hhblue');
                    }
                } else {
                    $( this ).prevUntil(endParent.children().first( 'span' ), 'span').add(endParent.children().first( 'span' )).addBack().each(function() {
                        $( this ).removeClass('bg-hhblue');
                    })
                    endParent.prevUntil( startParent ).each(function() {
                        $( this ).removeClass('bg-hhblue');
                    })
                    startParent.children( 'span' ).last().prevUntil( startWord, 'span' ).add(startWord).add(startParent.children( 'span' ).last()).each(function() {
                        $( this ).removeClass('bg-hhblue');
                    })
                }
            } else {
                $( noteEnd ).removeClass('bg-hhblue');
            };
        }
    })

    $('[shared-word]').on({
        mouseover: function() {
            var wordNum = $( this ).attr('shared-word');
            orig_elem = $( this );
            $('[shared-word="' + wordNum + '"]').addClass('chosen-word');
        },
        mouseout: function() {
            var wordNum = $( this ).attr('shared-word');
            $('[shared-word="' + wordNum + '"]').removeClass('chosen-word');
        }
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
    var extraStr = '';
    if (wordGraph) {
        extraStr = '<p>Press &lt;Enter&gt; to see collocates for <b>' + x.attr('inflected') + '</b></p>';
    }
//     lem_box.setAttribute("default-data", lem_box.innerHTML);
    if (lemma) {
        lem_box.innerHTML = lemma + extraStr;
    } else {
        lem_box.innerHTML = extraStr;
    }
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
        $('#' + urn + '-a1-row').css('height', 0)
        $('#' + urn + '-n1-row').css('height', 0)
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
        $('#' + c.replace(' ', '-') + '-row').css('height', 0)
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
        $('#' + urn + '-a1-row').css('height', $('#' + urn + '-a1-row').attr('oldHeight'))
        $('#' + urn + '-n1-row').css('height', $('#' + urn + '-n1-row').attr('oldHeight'))
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
        var noteRow = $('#' + c.replace(' ', '-') + '-row');
        noteRow.css('height', noteRow.attr('oldHeight'))
    };
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

function openWordGraphModal(targetWord, targetLemma, targetType, targetCorpus) {
    var wordGraphModal = $( '#word-graph-modal' );
    var extraParams = '';
    if ( targetCorpus ) {
        extraParams = '?corpus=' + targetCorpus;
    }
    console.log('params=' + extraParams);
    var request = new XMLHttpRequest();
    var subdomain = '';
    if (window.location.host == 'tools.formulae.uni-hamburg.de') {
        subdomain = '/dev'
    }
    request.onreadystatechange = function() {
        if (this.readyState == 4) {
            if (this.status == 200) {
                wordGraphModal.html(this.responseText);
                wordGraphModal.modal('show');
            } else {
                alert(message)
            }
        }
    };
    request.open('GET', subdomain + '/collocations/' + targetWord + '/' + targetLemma + '/None/' + targetType + extraParams, true);
    request.send()
}

function wordGraphMutualTexts(element, firstWord, wordLemma, secondWord, firstWordType, targetCorpus) {
    var extraParams = '';
    if ( targetCorpus ) {
        extraParams = '?corpus=' + targetCorpus;
    }
    var request = new XMLHttpRequest();
    var subdomain = '';
    if (window.location.host == 'tools.formulae.uni-hamburg.de') {
        subdomain = '/dev'
    }
    request.onreadystatechange = function() {
        if (this.readyState == 4) {
            if (this.status == 200) {
                $( element ).find('.card-body').html(this.responseText);
            } else {
                alert('There was a problem')
            }
        }
    };
    request.open('GET', subdomain + '/collocations/' + firstWord + '/' + wordLemma + '/' + secondWord + '/' + firstWordType + extraParams, true);
    request.send()
};
