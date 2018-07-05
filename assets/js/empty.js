var lexModal = document.getElementById('lexicon-modal')

function makePopupNote(id) {
    var popup = document.getElementById(id);
    popup.classList.toggle("show");
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
        request.onreadystatechange = function() {
            if (this.readyState == 4) {
                if (this.status == 200) {
                    lexModal.innerHTML = this.responseText;
                    lexModal.style.display = 'block';
                } else {
                    alert("Lexicon Entry for " + lemma + " not Found.")
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
