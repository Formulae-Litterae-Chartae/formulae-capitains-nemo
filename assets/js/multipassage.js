var lexModal = document.getElementById('lexicon-modal');

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
    var nodeclass = c + ' show'
    var matches = document.getElementsByClassName(nodeclass);
    while (matches.length > 0) {
        matches.item(0).setAttribute('aria-expanded', 'false');
        matches.item(0).classList.remove('show');
    }
    var elements = document.getElementById('header-' + c).querySelectorAll("[aria-describedby]");
    for (let element of elements) {
        element.click();
    }
}

function showNotes(c) {
    var matches = document.getElementsByClassName(c);
    for (var i=0; i<matches.length; i++) {
        matches[i].classList.add('show');
        matches[i].setAttribute('aria-expanded', 'true');
    }
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
    var noteCards = $('.note-card').length;
    var max = "70vh";
    if (noteCards == 2) {
        max = "34vh";
    } else if (noteCards > 2) {
        max = "22vh";
    }
    $('.note-card').css('max-height', max);
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
    $('#' + $(this).attr('toExpand')).toggleClass('expanded fade-out');
    if ($('#' + $(this).attr('toExpand')).hasClass('fade-out')) {
        $(this).attr('title', expMess);
    } else {
        $(this).attr('title', conMess);
    }
});

$('.expand').each(function() {
    $(this).attr('title', expMess);
});
