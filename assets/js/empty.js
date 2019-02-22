var lexModal = document.getElementById('lexicon-modal');

$(function () {
  $('[data-toggle="popover"]').popover()
})

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
    
function restrictSearch() {
    var button = document.getElementById('restrictSearchButton');
    var re = new RegExp('&corpus=[^&]*');
    var corpora = document.getElementsByClassName('corp-restrict-to');
    var oldUrl = button.getAttribute('href');
    var newCorpora = new Array();
    for (let corp of corpora){
        if (corp.checked) {
            newCorpora.push(corp.getAttribute('value'));
        }
    }
    button.setAttribute('href', oldUrl.replace(re, '&corpus=' + newCorpora.join('%2B') + '&old_search=True'));
}

function closeLexEntry() {
    lexModal.style.display = "none";
}
    
window.onclick = function(event) {
    if (event.target == lexModal) {
        lexModal.style.display = 'none';
    }
}

function getSubElements(coll) {
        var objectId = coll.getAttribute('sub-element-url');
        var targetList = document.getElementById(coll.getAttribute('sub-element-id'));
        if (coll.getAttribute('ul-shown') == 'true') {
            coll.setAttribute('ul-shown', 'false');
            targetList.innerHTML = ''
        } else {
            var request = new XMLHttpRequest();
            request.onreadystatechange = function() {
                if (this.readyState == 4) {
                    if (this.status == 200) {
                        targetList.innerHTML = this.responseText;
                        coll.setAttribute('ul-shown', 'true');
                    } else {
                        alert("No texts found for collection.")
                    }
                }
            };
            request.open('GET', objectId, true);
            request.send()
    }
}

// AJAX request to change locale and then refresh the page
$('.lang-link').bind('click', function(event) {
    event.preventDefault();
    e = this;
    var request = new XMLHttpRequest();
    request.onreadystatechange = function() {
        if (this.readyState == 4) {
            if (this.status == 200) {
                location.reload();
            } else {
                alert('Failed to change language')
            }
        }
    };
    request.open('GET', '/lang/' + e.getAttribute('value'), true);
    request.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    request.send()
})

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
        }
    });
});

// Expands and contracts the note when the expand arrow is clicked
$('.expand').click(function() {
    $('#' + $(this).attr('toExpand')).toggleClass('expanded');
});
