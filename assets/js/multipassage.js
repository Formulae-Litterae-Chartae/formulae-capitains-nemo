var lexModal = document.getElementById('lexicon-modal');
$('.apparatus-title').append(appHeading);
$('.commentary-title').append(comHeading);
$('[id$="a1-hide-button"]').attr('title', appCloseButton)
$('[id$="a1-show-button"]').attr('title', appOpenButton)
$('[id$="n1-hide-button"]').attr('title', comCloseButton)
$('[id$="n1-show-button"]').attr('title', comOpenButton)


// These are the popovers for the notes in the right column of the normal text view.
$(function () {
  $('[data-toggle="bibl-popover"]').popover(
      {placement: 'left', 
          boundary: 'window',
          template: '<div class="popover bibl-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    }
  )
})

$(function () {
  $('[data-toggle="charter-bibl-popover"]').popover(
      {placement: 'right', 
          boundary: 'window',
          template: '<div class="popover charter-bibl-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    }
  )
})

// These are the popups in the elexicon modal notes.
// This is required to initialize popovers that are not part of the DOM when the document is loaded.
// https://github.com/twbs/bootstrap/issues/4215
$(function () {
  $(document).popover(
      {selector: '.modal-popover',
          placement: 'top', 
          boundary: 'window',
          template: '<div class="popover elex-modal-popover" role="tooltip"><div class="arrow"></div><h3 class="popover-header"></h3><div class="popover-body"></div></div>',
          html: true
    }
  )
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
    var lemma = x.getAttribute("lemma");
    var lem_box = document.getElementById("lem_box");
    lem_box.setAttribute("default-data", lem_box.innerHTML);
    lem_box.innerHTML = lemma;
}

function hideLemma() {
    var lem_box = document.getElementById("lem_box");
    lem_box.innerHTML = lem_box.getAttribute("default-data");
    lem_box.removeAttribute("default-data");
}

//to disable cut, copy, paste, and mouse right-click
$(document).ready(function () {    
    //Disable cut, copy, and paste
    $('.no-copy').bind('cut copy paste', function (e) {
        e.preventDefault();
        $('#no-copy-message').modal('show')
    });
    
    //Disable right-mouse click
    $(".no-copy").on("contextmenu",function(e){
        return false;
    });
});

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
        var lemma = word.getAttribute('data-lexicon');
        var request = new XMLHttpRequest();
        var message = lexModal.getAttribute('message');
        request.onreadystatechange = function() {
            if (this.readyState == 4) {
                if (this.status == 200) {
                    lexModal.innerHTML = this.responseText;
                    lexModal.style.display = 'block';
                } else {
                    alert(message + lemma)
                }
            }
        };
        request.open('GET', '/lexicon/urn:cts:formulae:elexicon.' + lemma + '.deu001', true);
        request.send()
    }
    
function closeLexEntry() {
    lexModal.style.display = "none";
}
    
window.onclick = function(event) {
    if (event.target == lexModal) {
        lexModal.style.display = 'none';
    }
}

// Automatically set the max-height of the note-card for each text depending on the number of texts
$(function(){
    var noteCardsLeft = $('.noteCardLeft').length;
    var max = "70vh";
    if (noteCardsLeft == 2 ) {
        max = "34vh";
    } else if (noteCardsLeft > 2) {
        max = "22vh";
    }
    $('.noteCardLeft').css('max-height', max);
    var noteCardsRight = $('.noteCardRight').length;
    var max = "70vh";
    if (noteCardsRight == 2 ) {
        max = "34vh";
    } else if (noteCardsRight > 2) {
        max = "22vh";
    }
    $('.noteCardRight').css('max-height', max);
})

// Show expand icon only if the whole note is not shown. Thanks to http://jsfiddle.net/kedem/D9NCP/
$(function() {
    $('.two-line').each(function(index, element) {
        var noteHeight = $( element ).height();
        var textHeight = $( element ).find('.card').height();
        if (textHeight < noteHeight) {
            $( element ).find('.expand').hide();
            $( element ).removeClass('fade-out');
        }
    });
});

// Expands and contracts the note when the expand arrow is clicked
$('.expand').click(function() {
    $('#' + $(this).attr('toexpand')).toggleClass('expanded fade-out');
    if ($('#' + $(this).attr('toexpand')).hasClass('fade-out')) {
        $(this).attr('title', expMess);
    } else {
        $(this).attr('title', conMess);
    }
});

$('.expand').each(function() {
    $(this).attr('title', expMess);
});

$('.note').click(function() {
    var linkTarget = $(this).attr('href');
    $( linkTarget ).on("animationend", function() {this.classList.remove('flash-yellow')})
    $( linkTarget ).addClass( 'flash-yellow' );
    if ($(linkTarget).hasClass('fade-out')) {
        $(linkTarget).toggleClass('expanded fade-out');
        $( '[toexpand=' + linkTarget.replace('#', '') + ']' ).attr('title', conMess);
    }
});

function changeViewMode() {
    var textSections = document.querySelectorAll('.text-section');
    for (let section of textSections) {
        section.classList.toggle('scrolling');
    }
};
